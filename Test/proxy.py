#!/usr/bin/env python3
"""
proxy.py
Tugas yang diselesaikan:
1. Menjalankan Proxy Server berbasis TCP socket manual pada port 8080.
2. Menerima HTTP request dari client.
3. Melakukan parsing URL/path request.
4. Mengimplementasikan forwarding ke Web Server port 8000 jika cache MISS.
5. Mengimplementasikan cache lokal berbasis file jika cache HIT.
6. Mengembalikan response ke client.
7. Menangani error 502 Bad Gateway dan 504 Gateway Timeout.
8. Melayani banyak client simultan dengan threading.
9. Menjaga konsistensi cache sederhana dengan lock.

Catatan:
- Proxy ini hanya menangani HTTP GET sederhana.
- Tidak memakai requests, http.server, Flask, Django, FastAPI, atau library HTTP tingkat tinggi.
"""

import argparse
import hashlib
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# =========================
# Section 1 - Konfigurasi dasar
# =========================

BUFFER_SIZE = 8192
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 8080
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 8000
DEFAULT_CACHE_DIR = "proxy_cache"
UPSTREAM_TIMEOUT_SECONDS = 5

# Lock global untuk menghindari race condition saat cache file yang sama ditulis/dibaca bersamaan.
cache_lock = threading.Lock()


# =========================
# Section 2 - Utility umum
# Tugas:
# - Logging.
# - Membuat response error dari proxy.
# - Membaca status code dari response upstream.
# =========================

def now() -> str:
    """Menghasilkan timestamp untuk log."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    """Menampilkan log proxy dengan timestamp dan nama thread."""
    thread_name = threading.current_thread().name
    print(f"[{now()}] [PROXY] [{thread_name}] {message}", flush=True)


def build_http_response(status_code: int, reason: str, body: bytes) -> bytes:
    """Membuat response HTTP manual untuk error dari proxy."""
    headers = [
        f"HTTP/1.1 {status_code} {reason}",
        "Content-Type: text/html; charset=utf-8",
        f"Content-Length: {len(body)}",
        "Connection: close",
        "Server: ManualPythonSocketProxy/1.0",
    ]
    return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8") + body


def proxy_error_response(status_code: int, reason: str, detail: str) -> bytes:
    """Membuat halaman error proxy."""
    body = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{status_code} {reason}</title></head>
<body>
    <h1>{status_code} {reason}</h1>
    <p>{detail}</p>
</body>
</html>
""".encode("utf-8")
    return build_http_response(status_code, reason, body)


def get_status_code(response: bytes) -> int | None:
    """
    Mengambil status code dari response HTTP upstream.
    Contoh line pertama: HTTP/1.1 200 OK
    """
    try:
        first_line = response.split(b"\r\n", 1)[0].decode("iso-8859-1")
        parts = first_line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    except Exception:
        return None
    return None


# =========================
# Section 3 - Parsing HTTP request
# Tugas:
# - Membaca request line dari client.
# - Memvalidasi hanya metode GET.
# - Mengambil path URL.
# =========================

def parse_client_request(raw_request: bytes) -> Tuple[str, str, str, Dict[str, str]]:
    """
    Parsing request client.

    Return:
    (method, path, version, headers)

    Akan raise ValueError jika request malformed.
    """
    try:
        text = raw_request.decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise ValueError("Request tidak bisa didecode") from exc

    header_text = text.split("\r\n\r\n", 1)[0]
    lines = header_text.split("\r\n")

    if not lines or len(lines[0].split()) != 3:
        raise ValueError("Request line tidak valid")

    method, raw_path, version = lines[0].split()

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    if method.upper() != "GET":
        raise ValueError("Proxy ini hanya mendukung metode GET")

    if not version.startswith("HTTP/"):
        raise ValueError("HTTP version tidak valid")

    # Jika client/browser mengirim absolute URI, ambil path-nya saja.
    # Contoh: GET http://example.com/index.html HTTP/1.1
    path = raw_path
    if raw_path.startswith("http://") or raw_path.startswith("https://"):
        without_scheme = raw_path.split("://", 1)[1]
        slash_index = without_scheme.find("/")
        path = without_scheme[slash_index:] if slash_index != -1 else "/"

    if not path.startswith("/"):
        path = "/" + path

    return method.upper(), path, version, headers


def build_upstream_request(path: str, server_host: str, server_port: int) -> bytes:
    """
    Membuat request baru yang dikirim Proxy ke Web Server.

    Tugas yang diselesaikan:
    - Memastikan request ke webserver punya Host header server.
    - Connection: close agar pembacaan response sederhana sampai socket ditutup.
    """
    request_lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {server_host}:{server_port}",
        "Connection: close",
        "User-Agent: ManualPythonSocketProxy/1.0",
        "\r\n",
    ]
    return "\r\n".join(request_lines).encode("utf-8")


# =========================
# Section 4 - Cache berbasis file
# Tugas:
# - Menentukan nama file cache berdasarkan URL/path.
# - Mengecek cache HIT/MISS.
# - Membaca/menulis response HTTP lengkap ke cache.
# =========================

def cache_key_for_path(path: str) -> str:
    """
    Membuat nama file cache yang aman dari path URL.
    Hash dipakai agar nama file tidak mengandung slash atau karakter berbahaya.
    """
    return hashlib.sha256(path.encode("utf-8")).hexdigest() + ".cache"


def cache_path(cache_dir: Path, path: str) -> Path:
    """Menghasilkan path lengkap file cache untuk URL path tertentu."""
    return cache_dir / cache_key_for_path(path)


def read_cache(cache_dir: Path, path: str) -> bytes | None:
    """
    Membaca cache jika tersedia.
    Return None jika cache belum ada.
    """
    target = cache_path(cache_dir, path)

    with cache_lock:
        if not target.exists() or not target.is_file():
            return None
        return target.read_bytes()


def write_cache(cache_dir: Path, path: str, response: bytes) -> None:
    """
    Menulis response HTTP lengkap ke cache.

    Menggunakan file sementara lalu os.replace agar lebih aman saat multi-thread.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_path(cache_dir, path)
    temp = target.with_suffix(".tmp")

    with cache_lock:
        temp.write_bytes(response)
        os.replace(temp, target)


# =========================
# Section 5 - Forwarding ke Web Server
# Tugas:
# - Membuka TCP socket ke webserver.
# - Mengirim HTTP request.
# - Membaca seluruh response sampai koneksi ditutup.
# - Membedakan timeout dan error koneksi.
# =========================

def fetch_from_webserver(path: str, server_host: str, server_port: int) -> bytes:
    """
    Forward request ke webserver dan mengambil response.

    Raise TimeoutError untuk timeout.
    Raise OSError untuk connection refused/reset/dll.
    """
    upstream_request = build_upstream_request(path, server_host, server_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as upstream_socket:
        upstream_socket.settimeout(UPSTREAM_TIMEOUT_SECONDS)
        upstream_socket.connect((server_host, server_port))
        upstream_socket.sendall(upstream_request)

        chunks: list[bytes] = []
        while True:
            chunk = upstream_socket.recv(BUFFER_SIZE)
            if not chunk:
                break
            chunks.append(chunk)

    return b"".join(chunks)


# =========================
# Section 6 - Handler koneksi client
# Tugas:
# - Menerima request client.
# - Menentukan HIT/MISS.
# - Jika HIT: kirim dari cache.
# - Jika MISS: forward ke server, simpan cache jika berhasil, kirim ke client.
# - Mencatat waktu respons.
# =========================

def handle_client(
    client_socket: socket.socket,
    client_address: Tuple[str, int],
    server_host: str,
    server_port: int,
    cache_dir: Path,
) -> None:
    """
    Menangani satu koneksi dari client.
    Dijalankan di thread terpisah untuk mendukung multi-client.
    """
    client_ip, client_port = client_address
    start_time = time.perf_counter()

    with client_socket:
        try:
            raw_request = client_socket.recv(BUFFER_SIZE)

            if not raw_request:
                return

            try:
                _method, path, _version, _headers = parse_client_request(raw_request)
            except ValueError as exc:
                response = proxy_error_response(400, "Bad Request", str(exc))
                client_socket.sendall(response)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log(f"{client_ip}:{client_port} malformed request -> 400 ({elapsed_ms:.2f} ms)")
                return

            # Cache hanya disimpan untuk response sukses 200 OK.
            cached_response = read_cache(cache_dir, path)
            if cached_response is not None:
                client_socket.sendall(cached_response)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log(f"{client_ip}:{client_port} {path} cache=HIT response_time={elapsed_ms:.2f} ms")
                return

            # Cache MISS: forward request ke Web Server.
            try:
                upstream_response = fetch_from_webserver(path, server_host, server_port)
            except TimeoutError:
                response = proxy_error_response(
                    504,
                    "Gateway Timeout",
                    "Web Server tidak merespons dalam batas waktu yang ditentukan.",
                )
                client_socket.sendall(response)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log(f"{client_ip}:{client_port} {path} cache=MISS -> 504 response_time={elapsed_ms:.2f} ms")
                return
            except OSError as exc:
                response = proxy_error_response(
                    504,
                    "Gateway Timeout",
                    f"Web Server tidak dapat dihubungi: {exc}",
                )
                client_socket.sendall(response)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log(f"{client_ip}:{client_port} {path} cache=MISS -> 504 response_time={elapsed_ms:.2f} ms")
                return

            status_code = get_status_code(upstream_response)

            # Dokumen meminta jika server mengembalikan galat, proxy menangani sebagai 502 Bad Gateway.
            # Di sini, response 5xx dari server dipetakan menjadi 502.
            if status_code is not None and status_code >= 500:
                response = proxy_error_response(
                    502,
                    "Bad Gateway",
                    f"Web Server mengembalikan error upstream: {status_code}.",
                )
                client_socket.sendall(response)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                log(f"{client_ip}:{client_port} {path} cache=MISS upstream={status_code} -> 502 response_time={elapsed_ms:.2f} ms")
                return

            # Simpan cache hanya jika response 200 OK.
            if status_code == 200:
                write_cache(cache_dir, path, upstream_response)

            client_socket.sendall(upstream_response)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log(f"{client_ip}:{client_port} {path} cache=MISS upstream={status_code} response_time={elapsed_ms:.2f} ms")

        except Exception as exc:
            response = proxy_error_response(502, "Bad Gateway", "Terjadi error pada proxy saat memproses request.")
            try:
                client_socket.sendall(response)
            except OSError:
                pass
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log(f"{client_ip}:{client_port} -> 502 unexpected error: {exc} ({elapsed_ms:.2f} ms)")


# =========================
# Section 7 - Server utama proxy
# Tugas:
# - Bind ke port 8080.
# - Menerima koneksi dari client.
# - Membuat thread baru untuk setiap client.
# =========================

def start_proxy(
    listen_host: str,
    listen_port: int,
    server_host: str,
    server_port: int,
    cache_dir: Path,
) -> None:
    """Menjalankan proxy server TCP."""
    cache_dir.mkdir(parents=True, exist_ok=True)

    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_socket.bind((listen_host, listen_port))
    proxy_socket.listen(50)

    log(f"Proxy listening on {listen_host}:{listen_port}")
    log(f"Forward target Web Server: {server_host}:{server_port}")
    log(f"Cache directory: {cache_dir.resolve()}")

    while True:
        client_socket, client_address = proxy_socket.accept()
        worker = threading.Thread(
            target=handle_client,
            args=(client_socket, client_address, server_host, server_port, cache_dir),
            daemon=True,
            name=f"client-{client_address[0]}:{client_address[1]}",
        )
        worker.start()


# =========================
# Section 8 - Entry point program
# Tugas:
# - Membaca argument CLI.
# - Menjalankan proxy.
# =========================

def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Python Socket Proxy Server with File Cache")
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST, help="Host bind proxy, default: 0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT, help="Port proxy, default: 8080")
    parser.add_argument("--server-host", default=DEFAULT_SERVER_HOST, help="IP/host Web Server, default: 127.0.0.1")
    parser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT, help="Port HTTP Web Server, default: 8000")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="Folder cache proxy, default: proxy_cache")
    args = parser.parse_args()

    start_proxy(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        server_host=args.server_host,
        server_port=args.server_port,
        cache_dir=Path(args.cache_dir),
    )


if __name__ == "__main__":
    main()
