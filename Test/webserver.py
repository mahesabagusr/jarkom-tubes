#!/usr/bin/env python3
"""
webserver.py
Tugas yang diselesaikan:
1. Menjalankan HTTP Web Server berbasis TCP socket manual pada port 8000.
2. Melayani HTTP GET untuk file statis di folder yang sama dengan webserver.py.
3. Mengirim HTTP response valid: 200, 404, 400, 405, dan 500.
4. Menjalankan UDP Echo Server pada port 9000 untuk pengukuran QoS.
5. Menangani beberapa koneksi secara simultan dengan threading.

Catatan:
- Tidak memakai Flask/Django/FastAPI/http.server/requests.
- Semua komunikasi memakai modul socket bawaan Python.
"""

import argparse
import mimetypes
import os
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

# =========================
# Section 1 - Konfigurasi dasar
# =========================

BUFFER_SIZE = 8192
DEFAULT_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8000
DEFAULT_UDP_PORT = 9000


# =========================
# Section 2 - Utility umum
# Tugas:
# - Membuat timestamp log.
# - Membangun response HTTP manual.
# - Menentukan content type berdasarkan ekstensi file.
# =========================

def now() -> str:
    """Menghasilkan timestamp untuk kebutuhan logging."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    """Menampilkan log server dengan timestamp dan nama thread."""
    thread_name = threading.current_thread().name
    print(f"[{now()}] [WEB] [{thread_name}] {message}", flush=True)


def build_http_response(
    status_code: int,
    reason: str,
    body: bytes,
    content_type: str = "text/html; charset=utf-8",
    extra_headers: Dict[str, str] | None = None,
) -> bytes:
    """
    Membuat HTTP response valid secara manual.

    Tugas yang diselesaikan:
    - Format HTTP/1.1 response.
    - Menambahkan Content-Length agar client/proxy tahu ukuran body.
    - Menutup koneksi setelah response dikirim dengan header Connection: close.
    """
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        "Connection": "close",
        "Server": "ManualPythonSocketWebServer/1.0",
    }

    if extra_headers:
        headers.update(extra_headers)

    header_lines = [f"HTTP/1.1 {status_code} {reason}"]
    header_lines.extend(f"{key}: {value}" for key, value in headers.items())

    # HTTP memisahkan header dan body dengan CRLF ganda.
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8") + body


def error_response(status_code: int, reason: str, detail: str) -> bytes:
    """
    Membuat halaman error sederhana.
    Dipakai untuk 400, 404, 405, dan 500.
    """
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


def guess_content_type(path: Path) -> str:
    """
    Menentukan Content-Type dari file.
    Contoh:
    - .html -> text/html
    - .css  -> text/css
    - .js   -> text/javascript/application/javascript
    - .png  -> image/png
    """
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


# =========================
# Section 3 - Parsing HTTP request
# Tugas:
# - Membaca request line: GET /index.html HTTP/1.1
# - Mengambil method, path, version.
# - Mengambil header request.
# =========================

def parse_http_request(raw_request: bytes) -> Tuple[str, str, str, Dict[str, str]]:
    """
    Parsing HTTP request sederhana.

    Return:
    (method, path, version, headers)

    Akan raise ValueError jika request malformed.
    """
    try:
        text = raw_request.decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise ValueError("Request tidak bisa didecode") from exc

    # Header HTTP berakhir di CRLF ganda.
    header_text = text.split("\r\n\r\n", 1)[0]
    lines = header_text.split("\r\n")

    if not lines or len(lines[0].split()) != 3:
        raise ValueError("Request line tidak valid")

    method, path, version = lines[0].split()

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    return method, path, version, headers


def safe_resolve_path(root: Path, requested_path: str) -> Path:
    """
    Mengubah URL path menjadi path file lokal yang aman.

    Tugas yang diselesaikan:
    - "/" diarahkan ke "/index.html".
    - Query string diabaikan.
    - Mencegah directory traversal seperti /../../secret.txt.
    """
    clean_path = requested_path.split("?", 1)[0].split("#", 1)[0]

    if clean_path == "/":
        clean_path = "/index.html"

    # Hilangkan slash awal agar bisa digabung ke root.
    relative_path = clean_path.lstrip("/")

    # Resolve untuk mendapatkan absolute path final.
    target = (root / relative_path).resolve()
    root_resolved = root.resolve()

    # Pastikan target tetap berada di dalam root.
    if root_resolved not in target.parents and target != root_resolved:
        raise ValueError("Path tidak aman")

    return target


# =========================
# Section 4 - Handler HTTP TCP
# Tugas:
# - Menerima koneksi TCP.
# - Membaca HTTP request.
# - Mengirim file statis jika ada.
# - Mengirim error response jika request salah / file tidak ada.
# =========================

def handle_http_client(client_socket: socket.socket, client_address: Tuple[str, int], root: Path) -> None:
    """
    Menangani satu koneksi HTTP client/proxy.
    Fungsi ini dijalankan di thread terpisah agar server bisa melayani banyak client.
    """
    client_ip, client_port = client_address

    with client_socket:
        try:
            request_data = client_socket.recv(BUFFER_SIZE)

            if not request_data:
                return

            method, path, version, _headers = parse_http_request(request_data)

            if not version.startswith("HTTP/"):
                response = error_response(400, "Bad Request", "HTTP version tidak valid.")
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 400 Bad Request")
                return

            if method.upper() != "GET":
                response = error_response(405, "Method Not Allowed", "Server ini hanya mendukung metode GET.")
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 405 Method Not Allowed")
                return

            try:
                file_path = safe_resolve_path(root, path)
            except ValueError:
                response = error_response(400, "Bad Request", "Path request tidak aman atau tidak valid.")
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 400 Bad Request")
                return

            if not file_path.exists() or not file_path.is_file():
                response = error_response(404, "Not Found", f"Berkas '{path}' tidak ditemukan.")
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 404 Not Found")
                return

            try:
                body = file_path.read_bytes()
                content_type = guess_content_type(file_path)
                response = build_http_response(200, "OK", body, content_type=content_type)
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 200 OK ({len(body)} bytes)")
            except OSError as exc:
                response = error_response(500, "Internal Server Error", f"Gagal membaca file: {exc}")
                client_socket.sendall(response)
                log(f"{client_ip}:{client_port} {path} -> 500 Internal Server Error: {exc}")

        except ValueError as exc:
            response = error_response(400, "Bad Request", str(exc))
            client_socket.sendall(response)
            log(f"{client_ip}:{client_port} -> 400 Bad Request: {exc}")
        except Exception as exc:
            # Graceful error handling: server tidak crash saat ada error tak terduga.
            response = error_response(500, "Internal Server Error", "Terjadi error internal pada server.")
            try:
                client_socket.sendall(response)
            except OSError:
                pass
            log(f"{client_ip}:{client_port} -> 500 Internal Server Error: {exc}")


def start_http_server(host: str, port: int, root: Path) -> None:
    """
    Menjalankan HTTP TCP server.

    Tugas yang diselesaikan:
    - Bind ke host:port.
    - Listen koneksi masuk.
    - Spawn satu thread untuk setiap koneksi.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # SO_REUSEADDR membantu agar port cepat bisa dipakai ulang setelah program dihentikan.
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((host, port))
    server_socket.listen(50)

    log(f"HTTP server running on {host}:{port}, root={root.resolve()}")

    while True:
        client_socket, client_address = server_socket.accept()
        worker = threading.Thread(
            target=handle_http_client,
            args=(client_socket, client_address, root),
            daemon=True,
            name=f"http-{client_address[0]}:{client_address[1]}",
        )
        worker.start()


# =========================
# Section 5 - UDP Echo Server
# Tugas:
# - Membuka UDP socket.
# - Menerima paket UDP.
# - Mengirim balik payload yang sama.
# - Dipakai client.py untuk menghitung RTT, packet loss, jitter, throughput.
# =========================

def start_udp_echo_server(host: str, port: int) -> None:
    """
    Menjalankan UDP echo server.
    UDP tidak connection-oriented, jadi tidak ada accept().
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((host, port))

    log(f"UDP echo server running on {host}:{port}")

    while True:
        try:
            data, address = udp_socket.recvfrom(BUFFER_SIZE)
            udp_socket.sendto(data, address)
            log(f"UDP echo {len(data)} bytes to {address[0]}:{address[1]}")
        except Exception as exc:
            # Server tetap hidup walaupun satu paket gagal diproses.
            log(f"UDP error: {exc}")


# =========================
# Section 6 - Entry point program
# Tugas:
# - Membaca argument CLI.
# - Menjalankan HTTP server dan UDP server bersamaan.
# =========================

def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Python Socket Web Server + UDP Echo Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host bind server, default: 0.0.0.0")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT, help="Port HTTP TCP, default: 8000")
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT, help="Port UDP Echo, default: 9000")
    parser.add_argument("--root", default=".", help="Folder asset HTML/resource, default: folder saat ini")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root folder tidak valid: {root}")

    # Jalankan HTTP server di thread daemon.
    http_thread = threading.Thread(
        target=start_http_server,
        args=(args.host, args.http_port, root),
        daemon=True,
        name="http-main",
    )
    http_thread.start()

    # Jalankan UDP server di main thread agar proses tetap hidup.
    start_udp_echo_server(args.host, args.udp_port)


if __name__ == "__main__":
    main()
