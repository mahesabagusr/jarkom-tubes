#!/usr/bin/env python3
"""
client.py
Tugas yang diselesaikan:
1. Mode TCP/HTTP:
   - Mengirim HTTP GET ke Proxy Server port 8080.
   - Menerima dan menampilkan response HTML/HTTP di terminal.
2. Mode UDP/QoS:
   - Mengirim minimal 10 paket UDP ke Web Server port 9000.
   - Format payload: "Ping <seq> <timestamp>".
   - Menghitung RTT per paket.
   - Menghitung Min/Avg/Max RTT, Packet Loss, Jitter, dan Throughput.
3. Mode multi:
   - Menjalankan beberapa request HTTP konkuren untuk pengujian 5 client simultan.

Catatan:
- HTTP wajib melalui proxy.
- UDP QoS dikirim ke UDP echo server pada webserver.py.
- Tidak memakai requests atau library HTTP tingkat tinggi.
"""

import argparse
import socket
import statistics
import threading
import time
from datetime import datetime
from typing import List, Tuple

# =========================
# Section 1 - Konfigurasi dasar
# =========================

BUFFER_SIZE = 8192
DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 8080
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 9000
DEFAULT_TIMEOUT_SECONDS = 1.0


# =========================
# Section 2 - Utility umum
# Tugas:
# - Logging.
# - Membuat request HTTP manual.
# - Membaca response sampai koneksi ditutup.
# =========================

def now() -> str:
    """Menghasilkan timestamp untuk log client."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    """Menampilkan log client dengan timestamp dan nama thread."""
    thread_name = threading.current_thread().name
    print(f"[{now()}] [CLIENT] [{thread_name}] {message}", flush=True)


def build_http_get_request(path: str, host: str, port: int) -> bytes:
    """
    Membuat HTTP GET request manual.

    Tugas yang diselesaikan:
    - Client mengakses Proxy, bukan Web Server.
    - Host header diarahkan ke proxy.
    - Connection: close agar response mudah dibaca sampai socket ditutup.
    """
    if not path.startswith("/"):
        path = "/" + path

    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}:{port}",
        "Connection: close",
        "User-Agent: ManualPythonSocketClient/1.0",
        "\r\n",
    ]
    return "\r\n".join(lines).encode("utf-8")


def receive_all(sock: socket.socket) -> bytes:
    """Membaca seluruh data dari socket sampai server/proxy menutup koneksi."""
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(BUFFER_SIZE)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


# =========================
# Section 3 - Mode TCP/HTTP
# Tugas:
# - Connect ke Proxy.
# - Kirim GET request.
# - Terima response.
# - Tampilkan response di terminal.
# =========================

def run_http_client(proxy_host: str, proxy_port: int, path: str, print_body: bool = True) -> Tuple[bytes, float]:
    """
    Menjalankan satu request HTTP ke proxy.

    Return:
    (response_bytes, elapsed_ms)
    """
    request = build_http_get_request(path, proxy_host, proxy_port)
    start_time = time.perf_counter()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect((proxy_host, proxy_port))
        sock.sendall(request)
        response = receive_all(sock)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    if print_body:
        print("=" * 80)
        print(f"HTTP response from proxy {proxy_host}:{proxy_port} for path {path}")
        print(f"Response time: {elapsed_ms:.2f} ms")
        print("=" * 80)
        print(response.decode("utf-8", errors="replace"))

    return response, elapsed_ms


# =========================
# Section 4 - Mode UDP/QoS
# Tugas:
# - Kirim paket UDP periodik ke webserver.
# - Ukur RTT untuk setiap echo.
# - Catat timeout sebagai packet loss.
# - Hitung statistik akhir.
# =========================

def calculate_jitter(rtts_ms: List[float]) -> float:
    """
    Menghitung jitter sebagai standar deviasi dari selisih RTT berturut-turut.
    Jika data kurang, jitter = 0.
    """
    if len(rtts_ms) < 2:
        return 0.0

    deltas = [abs(rtts_ms[i] - rtts_ms[i - 1]) for i in range(1, len(rtts_ms))]

    if len(deltas) < 2:
        return deltas[0]

    return statistics.stdev(deltas)


def run_udp_qos_client(server_host: str, udp_port: int, count: int, timeout: float, interval: float) -> None:
    """
    Menjalankan UDP QoS test.

    Output wajib:
    - RTT per paket atau Request timed out.
    - Statistik akhir: Min/Avg/Max RTT, Packet Loss, Jitter, Throughput.
    """
    sent_packets = 0
    received_packets = 0
    rtts_ms: List[float] = []
    total_payload_bytes_received = 0

    test_start = time.perf_counter()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)

        for seq in range(1, count + 1):
            send_timestamp = time.time()
            payload_text = f"Ping {seq} {send_timestamp}"
            payload = payload_text.encode("utf-8")

            sent_packets += 1
            packet_start = time.perf_counter()

            try:
                sock.sendto(payload, (server_host, udp_port))
                data, address = sock.recvfrom(BUFFER_SIZE)

                packet_end = time.perf_counter()
                rtt_ms = (packet_end - packet_start) * 1000

                received_packets += 1
                total_payload_bytes_received += len(data)
                rtts_ms.append(rtt_ms)

                print(f"Reply from {address[0]}:{address[1]} seq={seq} bytes={len(data)} RTT={rtt_ms:.2f} ms")

            except socket.timeout:
                print(f"Request timed out seq={seq}")

            time.sleep(interval)

    test_end = time.perf_counter()
    duration_seconds = max(test_end - test_start, 0.000001)

    lost_packets = sent_packets - received_packets
    packet_loss_percent = (lost_packets / sent_packets) * 100 if sent_packets else 0.0

    if rtts_ms:
        min_rtt = min(rtts_ms)
        avg_rtt = sum(rtts_ms) / len(rtts_ms)
        max_rtt = max(rtts_ms)
        jitter = calculate_jitter(rtts_ms)
    else:
        min_rtt = avg_rtt = max_rtt = jitter = 0.0

    throughput_kbps = (total_payload_bytes_received * 8) / duration_seconds / 1000

    print("\n" + "=" * 80)
    print("UDP QoS Statistics")
    print("=" * 80)
    print(f"Destination       : {server_host}:{udp_port}")
    print(f"Packets sent      : {sent_packets}")
    print(f"Packets received  : {received_packets}")
    print(f"Packets lost      : {lost_packets}")
    print(f"Packet loss       : {packet_loss_percent:.2f}%")
    print(f"RTT min           : {min_rtt:.2f} ms")
    print(f"RTT avg           : {avg_rtt:.2f} ms")
    print(f"RTT max           : {max_rtt:.2f} ms")
    print(f"Jitter            : {jitter:.2f} ms")
    print(f"Throughput        : {throughput_kbps:.2f} kbps")
    print(f"Duration          : {duration_seconds:.2f} s")


# =========================
# Section 5 - Mode Multi-client
# Tugas:
# - Menjalankan beberapa request HTTP secara bersamaan.
# - Dipakai untuk memenuhi skenario minimal 5 client konkuren.
# =========================

def multi_worker(index: int, proxy_host: str, proxy_port: int, path: str) -> None:
    """Worker untuk satu client virtual pada mode multi."""
    try:
        _response, elapsed_ms = run_http_client(proxy_host, proxy_port, path, print_body=False)
        log(f"client-{index} path={path} success response_time={elapsed_ms:.2f} ms")
    except Exception as exc:
        log(f"client-{index} path={path} failed: {exc}")


def run_multi_client(proxy_host: str, proxy_port: int, paths: List[str], clients: int) -> None:
    """
    Menjalankan beberapa client konkuren.
    Jika jumlah paths lebih sedikit dari jumlah client, path akan dipakai berulang.
    """
    threads: list[threading.Thread] = []
    start_time = time.perf_counter()

    for i in range(clients):
        path = paths[i % len(paths)]
        thread = threading.Thread(
            target=multi_worker,
            args=(i + 1, proxy_host, proxy_port, path),
            name=f"multi-{i + 1}",
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log(f"multi-client test selesai: {clients} clients, total_time={elapsed_ms:.2f} ms")


# =========================
# Section 6 - Entry point program
# Tugas:
# - Membaca mode dari CLI.
# - Menjalankan mode tcp, udp, atau multi.
# =========================

def main() -> None:
    parser = argparse.ArgumentParser(description="Manual Python Socket Client for HTTP Proxy and UDP QoS")
    parser.add_argument(
        "--mode",
        choices=["tcp", "udp", "multi"],
        required=True,
        help="Mode client: tcp untuk HTTP, udp untuk QoS, multi untuk multi-client HTTP",
    )

    # Argument untuk mode TCP dan multi.
    parser.add_argument("--proxy-host", default=DEFAULT_PROXY_HOST, help="IP/host Proxy Server, default: 127.0.0.1")
    parser.add_argument("--proxy-port", type=int, default=DEFAULT_PROXY_PORT, help="Port Proxy Server, default: 8080")
    parser.add_argument("--path", default="/index.html", help="Path resource HTTP, default: /index.html")

    # Argument untuk mode UDP.
    parser.add_argument("--server-host", default=DEFAULT_SERVER_HOST, help="IP/host UDP Web Server, default: 127.0.0.1")
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT, help="Port UDP Echo Server, default: 9000")
    parser.add_argument("--count", type=int, default=10, help="Jumlah paket UDP, minimal 10 disarankan")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout UDP per paket, default: 1 detik")
    parser.add_argument("--interval", type=float, default=0.2, help="Jeda antar paket UDP, default: 0.2 detik")

    # Argument khusus multi-client.
    parser.add_argument("--clients", type=int, default=5, help="Jumlah client konkuren untuk mode multi, default: 5")
    parser.add_argument(
        "--paths",
        default="/index.html,/index.html,/missing.html,/page.html,/index.html",
        help="Daftar path dipisah koma untuk mode multi",
    )

    args = parser.parse_args()

    if args.mode == "tcp":
        run_http_client(args.proxy_host, args.proxy_port, args.path, print_body=True)

    elif args.mode == "udp":
        if args.count < 10:
            log("Peringatan: dokumen meminta minimal 10 paket UDP. Count dinaikkan menjadi 10.")
            args.count = 10
        run_udp_qos_client(args.server_host, args.udp_port, args.count, args.timeout, args.interval)

    elif args.mode == "multi":
        paths = [path.strip() for path in args.paths.split(",") if path.strip()]
        if not paths:
            paths = [args.path]
        run_multi_client(args.proxy_host, args.proxy_port, paths, args.clients)


if __name__ == "__main__":
    main()
