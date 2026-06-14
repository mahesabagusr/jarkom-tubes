import socket
import time
import sys
import statistics
import csv
import os
import datetime
import threading

PROXY_HOST = '127.0.0.1'
PROXY_PORT = 8080
SERVER_HOST = '127.0.0.1'
SERVER_UDP_PORT = 9090

CSV_LOG_PATH = "qos_log.csv"

def tcp_client(path="/index.html"):
    print(f"Mengirim HTTP GET request untuk {path} via Proxy...")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        start_time = time.time()
        client.connect((PROXY_HOST, PROXY_PORT))
        request = f"GET {path} HTTP/1.1\r\nHost: {PROXY_HOST}\r\n\r\n"
        client.sendall(request.encode('utf-8'))

        response = b""
        while True:
            data = client.recv(4096)
            if not data:
                break
            response += data

        end_time = time.time()
        print(response.decode('utf-8', errors='ignore'))
        print(f"\n[*] Waktu respons: {(end_time - start_time)*1000:.2f} ms")
    except Exception as e:
        print(f"Koneksi gagal: {e}")
    finally:
        client.close()


def _http_request(path):
    """Kirim satu HTTP GET via Proxy secara senyap.

    Mengembalikan tuple (ok: bool, elapsed_ms: float, info: str).
    Dipakai oleh uji konkurensi agar output tiap client ringkas.
    """
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(10.0)
    start = time.time()
    try:
        client.connect((PROXY_HOST, PROXY_PORT))
        request = f"GET {path} HTTP/1.1\r\nHost: {PROXY_HOST}\r\n\r\n"
        client.sendall(request.encode('utf-8'))

        response = b""
        while True:
            data = client.recv(4096)
            if not data:
                break
            response += data

        elapsed = (time.time() - start) * 1000
        if response:
            status = response.split(b"\r\n", 1)[0].decode('utf-8', errors='ignore')
        else:
            status = "Tidak ada respons"
        return True, elapsed, status
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return False, elapsed, f"Error: {e}"
    finally:
        client.close()


def concurrent_clients(num_clients, path="/index.html"):
    """Kirim HTTP GET dari sejumlah client secara bersamaan (uji konkurensi)."""
    print(f"\nMengirim {num_clients} HTTP GET bersamaan untuk {path} via Proxy...\n")

    results = []
    print_lock = threading.Lock()

    def worker(idx):
        ok, elapsed, info = _http_request(path)
        with print_lock:
            results.append((idx, ok, elapsed, info))
            tag = "OK   " if ok else "GAGAL"
            print(f"  Client #{idx:<3} [{tag}] {elapsed:8.2f} ms | {info}")

    threads = []
    test_start = time.time()
    for i in range(1, num_clients + 1):
        t = threading.Thread(target=worker, args=(i,), name=f"LoadClient-{i}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_ms = (time.time() - test_start) * 1000

    # ── Statistik ────────────────────────────────────────────────
    successes = [r for r in results if r[1]]
    failures = [r for r in results if not r[1]]
    times = [r[2] for r in successes]

    print("\n--- Ringkasan Uji Konkurensi ---")
    print(f"Total client     : {num_clients}")
    print(f"Berhasil         : {len(successes)}")
    print(f"Gagal            : {len(failures)}")
    if times:
        print(f"Waktu respons    : Min {min(times):.2f} ms | "
              f"Avg {statistics.mean(times):.2f} ms | Max {max(times):.2f} ms")
    print(f"Total durasi     : {total_ms:.2f} ms (seluruh client berjalan paralel)")
    throughput = (len(successes) / (total_ms / 1000.0)) if total_ms > 0 else 0.0
    print(f"Throughput       : {throughput:.2f} request/detik")

def udp_pinger():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(1.0)  # Maksimal 1 detik timeout per paket

    rtt_list = []
    packets_sent = 10
    packets_lost = 0
    total_bytes_received = 0

    # Header CSV (buat file baru jika belum ada)
    write_header = not os.path.exists(CSV_LOG_PATH)
    csv_rows = []  # Kumpulkan dulu, tulis setelah selesai

    print(f"Mengirim {packets_sent} paket UDP ke {SERVER_HOST}:{SERVER_UDP_PORT}\n")
    test_start = time.time()

    for i in range(1, packets_sent + 1):
        send_time = time.time()
        message = f"Ping {i} {send_time}"
        row = {
            "session_start": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seq": i,
            "status": "",
            "rtt_ms": "",
            "bytes_received": ""
        }

        try:
            client.sendto(message.encode('utf-8'), (SERVER_HOST, SERVER_UDP_PORT))
            data, server = client.recvfrom(1024)
            recv_time = time.time()

            rtt = (recv_time - send_time) * 1000  # dalam milisekon
            rtt_list.append(rtt)
            total_bytes_received += len(data)

            row["status"] = "received"
            row["rtt_ms"] = f"{rtt:.4f}"
            row["bytes_received"] = len(data)

            print(f"Paket {i}: Balasan diterima dari {server[0]}, RTT = {rtt:.2f} ms")

        except socket.timeout:
            packets_lost += 1
            row["status"] = "timeout"
            print(f"Paket {i}: Request timed out")

        csv_rows.append(row)
        # Jeda 100ms antar paket agar pengiriman bersifat periodik
        time.sleep(0.1)

    test_end = time.time()
    duration = test_end - test_start

    # Kalkulasi Statistik Akhir
    print("\n--- Statistik QoS Ping UDP ---")
    min_rtt = avg_rtt = max_rtt = jitter = throughput = 0.0

    if rtt_list:
        min_rtt = min(rtt_list)
        avg_rtt = statistics.mean(rtt_list)
        max_rtt = max(rtt_list)
        print(f"RTT -> Min: {min_rtt:.2f} ms | Avg: {avg_rtt:.2f} ms | Max: {max_rtt:.2f} ms")

        if len(rtt_list) > 1:
            diffs = [rtt_list[j] - rtt_list[j-1] for j in range(1, len(rtt_list))]
            jitter = statistics.stdev(diffs) if len(diffs) > 1 else abs(diffs[0])
            print(f"Jitter (Standar deviasi selisih RTT): {jitter:.2f} ms")
        else:
            print("Jitter: N/A (terlalu sedikit paket)")
    else:
        print("RTT: N/A (semua paket hilang)")

    loss_pct = (packets_lost / packets_sent) * 100
    total_bits = total_bytes_received * 8
    throughput = (total_bits / 1000.0) / duration if duration > 0 else 0.0

    print(f"Packet Loss: {loss_pct:.2f}%")
    print(f"Throughput : {throughput:.4f} kbps")

    # Tulis ke CSV
    with open(CSV_LOG_PATH, 'a', newline='') as csvfile:
        fieldnames = ["session_start", "seq", "status", "rtt_ms", "bytes_received"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        writer.writerows(csv_rows)

        # Baris ringkasan sesi
        writer.writerow({
            "session_start": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "seq": "SUMMARY",
            "status": f"loss={loss_pct:.2f}% jitter={jitter:.2f}ms throughput={throughput:.4f}kbps",
            "rtt_ms": f"min={min_rtt:.2f} avg={avg_rtt:.2f} max={max_rtt:.2f}",
            "bytes_received": total_bytes_received
        })

    print(f"\n[OK] Log QoS disimpan ke: {CSV_LOG_PATH}")
    client.close()


def show_menu():
    print("\n" + "="*50)
    print("  CLIENT - Sistem Jaringan Komputer")
    print("  Client-Proxy-Server | Universitas Telkom")
    print("="*50)
    print("  [1] HTTP GET via Proxy (TCP)")
    print("  [2] UDP QoS Ping Test")
    print("  [3] HTTP GET resource tertentu via Proxy")
    print("  [0] Keluar")
    print("="*50)

def menu_tcp():
    path = input("  Masukkan path resource (default: /index.html): ").strip()
    if not path:
        path = "/index.html"
    if not path.startswith("/"):
        path = "/" + path
    tcp_client(path)

def menu_udp():
    print("  Memulai UDP QoS Ping Test ke server...")
    udp_pinger()

def menu_concurrent():
    raw = input("  Jumlah client bersamaan (default: 10): ").strip()
    try:
        num = int(raw) if raw else 10
    except ValueError:
        print("  [!] Input tidak valid, menggunakan 10.")
        num = 10
    if num < 1:
        print("  [!] Minimal 1 client, menggunakan 1.")
        num = 1
    path = input("  Path resource (default: /index.html): ").strip()
    if not path:
        path = "/index.html"
    if not path.startswith("/"):
        path = "/" + path
    concurrent_clients(num, path)


def menu_http():
    """Submenu untuk Choice [1]: pilih mode Single atau Multi."""
    print("\n  --- HTTP GET via Proxy ---")
    print("  [1] Single  (1 client, satu thread)")
    print("  [2] Multi   (banyak client, request bersamaan)")
    print("  [0] Kembali")
    sub = input("  Pilih mode: ").strip()

    if sub == "1":
        tcp_client("/index.html")
    elif sub == "2":
        menu_concurrent()
    elif sub == "0":
        return
    else:
        print("  [!] Pilihan tidak valid.")


if __name__ == "__main__":
    # Tetap dukung argumen CLI untuk kompatibilitas pengujian otomatis
    if len(sys.argv) > 1:
        mode = None
        path = "/index.html"

        # Parsing argumen secara fleksibel untuk mendukung -, --, en-dash, em-dash
        for i in range(1, len(sys.argv)):
            arg = sys.argv[i]
            clean_arg = arg.lstrip('-\u2013\u2014').lower()
            if clean_arg == "mode" and i + 1 < len(sys.argv):
                mode = sys.argv[i + 1].lstrip('-\u2013\u2014').lower()
            elif arg.lower() in ["tcp", "udp"] and mode is None:
                mode = arg.lower()
            elif arg.startswith("/"):
                path = arg

        if mode == "tcp":
            tcp_client(path)
        elif mode == "udp":
            udp_pinger()
        else:
            print("Penggunaan: python client.py [--mode tcp|udp] [/path]")
            sys.exit(1)
    else:
        # Mode menu interaktif
        while True:
            show_menu()
            choice = input("  Pilih menu: ").strip()

            if choice == "1":
                menu_http()
            elif choice == "2":
                menu_udp()
            elif choice == "3":
                menu_tcp()
            elif choice == "0":
                print("  Keluar dari program. Sampai jumpa!")
                sys.exit(0)
            else:
                print("  [!] Pilihan tidak valid. Silakan coba lagi.")
