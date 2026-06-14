# Revisi Tugas Besar Jaringan Komputer – Modul 8
**Implementasi Client–Proxy–Server Berbasis Socket Python**  
Laboratorium Praktikum Informatika – Universitas Telkom

---

## Ringkasan Revisi

| # | Poin Revisi | File Terdampak |
|---|-------------|----------------|
| 1 | Multi-threading eksplisit pada TCP dan UDP | `webserver.py`, `proxy.py` |
| 2 | Menu/navigasi interaktif di client | `client.py` |
| 3 | Arah akses browser ke Web Server (via Proxy) | `webserver.py`, `proxy.py` |
| 4 | Port UDP dikoreksi: `9000 → 9090` | semua file |
| 5 | Error handling diperkuat di Proxy | `proxy.py` |
| 6 | Log QoS disimpan ke file CSV | `client.py` |

---

## 1. Multi-threading pada TCP dan UDP (`webserver.py` & `proxy.py`)

### Masalah Sebelumnya
- `webserver.py` sudah menggunakan `threading.Thread` untuk TCP, namun thread UDP berjalan dalam loop tunggal tanpa konkurensi yang terlihat eksplisit di log.
- `proxy.py` sudah multi-thread per koneksi, namun tidak ada log yang menyebutkan ID thread aktif, sehingga sulit diverifikasi saat pengujian multi-client.

### Revisi `webserver.py`

Tambahkan log thread ID pada setiap handler agar bukti konkurensi tercatat:

```python
import threading

def handle_tcp_client(client_socket, client_address):
    thread_id = threading.current_thread().name  # Tambahan
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] TCP Thread [{thread_id}]: Handling connection from {client_address[0]}:{client_address[1]}")
    # ... sisa logika handler tidak berubah ...

def tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, TCP_PORT))
    server.listen(5)
    print(f"[*] TCP Server listening on {HOST}:{TCP_PORT}")

    while True:
        client_sock, addr = server.accept()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] TCP: Connection accepted from {addr[0]}:{addr[1]}. Spawning thread...")
        client_thread = threading.Thread(
            target=handle_tcp_client,
            args=(client_sock, addr),
            name=f"TCP-{addr[0]}-{addr[1]}"  # Nama thread deskriptif
        )
        client_thread.daemon = True  # Agar tidak menghalangi shutdown
        client_thread.start()

def udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, UDP_PORT))  # UDP_PORT = 9090
    print(f"[*] UDP Echo Server listening on {HOST}:{UDP_PORT}")

    while True:
        data, addr = server.recvfrom(1024)
        # Tangani setiap echo UDP di thread terpisah agar tidak blocking
        udp_thread = threading.Thread(
            target=lambda d=data, a=addr: server.sendto(d, a),
            name=f"UDP-{addr[0]}-{addr[1]}"
        )
        udp_thread.daemon = True
        udp_thread.start()

if __name__ == "__main__":
    print("[*] Server running on port 8000 (TCP) / 9090 (UDP), multithreading aktif")
    t1 = threading.Thread(target=tcp_server, name="TCPServer-Main")
    t2 = threading.Thread(target=udp_server, name="UDPServer-Main")
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()
    t1.join()
    t2.join()
```

### Revisi `proxy.py`

Tambahkan nama thread dan log ID agar log membuktikan thread-per-connection:

```python
def handle_client(client_socket, client_addr):
    thread_id = threading.current_thread().name  # Tambahan
    start_time = time.time()
    # ... parsing request seperti sebelumnya ...

    # Pada setiap log, sertakan thread_id:
    print(f"[{timestamp}] [{thread_id}] Proxy: {client_addr[0]} requested {url} - Cache HIT ...")
    print(f"[{timestamp}] [{thread_id}] Proxy: {client_addr[0]} requested {url} - Cache MISS ...")

def start_proxy():
    proxy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_server.bind((PROXY_HOST, PROXY_PORT))
    proxy_server.listen(10)
    print(f"[*] Proxy listening on {PROXY_HOST}:{PROXY_PORT}, multithreading aktif")

    while True:
        client_sock, addr = proxy_server.accept()
        thread = threading.Thread(
            target=handle_client,
            args=(client_sock, addr),
            name=f"Proxy-{addr[0]}-{addr[1]}"  # Nama thread deskriptif
        )
        thread.daemon = True
        thread.start()
```

---

## 2. Menu / Navigasi Interaktif di `client.py`

### Masalah Sebelumnya
Client hanya bisa dijalankan dengan argumen CLI (`--mode tcp` / `--mode udp`). Tidak ada menu interaktif, membuat pengujian kurang fleksibel dan sulit didemonstrasikan.

### Revisi `client.py`

Ganti blok `if __name__ == "__main__"` dengan menu interaktif berbasis loop:

```python
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

if __name__ == "__main__":
    # Tetap dukung argumen CLI untuk kompatibilitas pengujian otomatis
    if len(sys.argv) > 1:
        mode = None
        path = "/index.html"
        for i in range(1, len(sys.argv)):
            arg = sys.argv[i]
            clean_arg = arg.lstrip('-–—').lower()
            if clean_arg == "mode" and i + 1 < len(sys.argv):
                mode = sys.argv[i + 1].lstrip('-–—').lower()
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
                tcp_client("/index.html")
            elif choice == "2":
                menu_udp()
            elif choice == "3":
                menu_tcp()
            elif choice == "0":
                print("  Keluar dari program. Sampai jumpa!")
                sys.exit(0)
            else:
                print("  [!] Pilihan tidak valid. Silakan coba lagi.")
```

---

## 3. Akses Browser Diarahkan ke Web Server via Proxy

### Masalah Sebelumnya
- Browser bisa langsung mengakses `http://127.0.0.1:8000` dan melewati proxy, yang melanggar ketentuan topologi.
- `webserver.py` tidak melakukan pembatasan apa pun terhadap koneksi langsung dari selain Proxy.

### Revisi `webserver.py` – Pembatasan Akses Langsung

Tambahkan validasi IP sumber pada TCP handler agar hanya Proxy yang dapat mengakses Web Server secara langsung. Untuk pengujian browser, arahkan browser ke alamat Proxy (`http://127.0.0.1:8080`), bukan ke Web Server.

```python
ALLOWED_PROXY_IP = '127.0.0.1'  # IP Proxy yang diizinkan

def handle_tcp_client(client_socket, client_address):
    # Validasi: hanya terima koneksi dari IP Proxy
    if client_address[0] != ALLOWED_PROXY_IP:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] DITOLAK: Koneksi langsung dari {client_address[0]} (bukan Proxy)")
        error_body = b"<html><body><h1>403 Forbidden</h1><p>Akses langsung tidak diizinkan. Gunakan Proxy.</p></body></html>"
        header = "HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\n"
        header += f"Content-Length: {len(error_body)}\r\n\r\n"
        client_socket.sendall(header.encode() + error_body)
        client_socket.close()
        return
    # ... sisa handler seperti semula ...
```

### Cara Akses Browser yang Benar

Sesuai dokumen (Bagian F, Skenario 4 – Verifikasi Browser):

```
URL Browser: http://127.0.0.1:8080/index.html
             ^^^^^^^^^^^^^^^^^^^^^^^^^
             Alamat PROXY, bukan Web Server
```

> **Catatan:** Proxy sudah mendukung absolute URL (`http://...`), sehingga browser yang mengarah ke Proxy akan langsung diteruskan ke Web Server. Ini sesuai ketentuan bahwa "Web Server tidak dapat diakses langsung melalui antarmuka jaringan client" (Dokumen hal. 10).

---

## 4. Koreksi Port UDP: `9000 → 9090`

### Masalah
Dokumen tugas (Bagian E, hal. 8–9) menetapkan port UDP di `9000`, namun berdasarkan revisi ini port diubah ke **`9090`** untuk menghindari konflik dengan port lain yang umum digunakan.

> Jika dosen/asisten menetapkan port berbeda, sesuaikan konstanta berikut di seluruh file.

### Perubahan di Semua File

**`webserver.py`:**
```python
# SEBELUM:
UDP_PORT = 9000

# SESUDAH:
UDP_PORT = 9090
```

**`proxy.py`** (jika ada referensi ke UDP port server):
```python
SERVER_UDP_PORT = 9090  # Tambahkan jika proxy perlu meneruskan UDP
```

**`client.py`:**
```python
# SEBELUM:
SERVER_UDP_PORT = 9000

# SESUDAH:
SERVER_UDP_PORT = 9090
```

### Verifikasi Konfigurasi Port Akhir

| Komponen | Protokol | Port |
|----------|----------|------|
| Web Server (HTTP) | TCP | 8000 |
| Web Server (UDP Echo) | UDP | **9090** |
| Proxy Server | TCP | 8080 |
| Client | TCP/UDP | Ephemeral |

---

## 5. Error Handling Diperkuat di `proxy.py`

### Masalah Sebelumnya
- Error handling hanya menangkap `socket.timeout` dan `ConnectionRefusedError`.
- Request HTTP yang malformed (tidak ada spasi, header tidak lengkap) menyebabkan `IndexError` dan proxy crash.
- Tidak ada penanganan untuk koneksi yang ditutup tiba-tiba oleh client (broken pipe).

### Revisi `proxy.py` – Fungsi `handle_client` Lengkap

```python
def handle_client(client_socket, client_addr):
    thread_id = threading.current_thread().name
    start_time = time.time()

    try:
        client_socket.settimeout(10.0)  # Timeout baca dari client
        request = client_socket.recv(4096)

        if not request:
            return

        # ── Parsing request ──────────────────────────────────────────
        try:
            first_line = request.split(b'\r\n')[0]
            parts = first_line.split(b' ')
            if len(parts) < 2:
                raise ValueError("Malformed HTTP request line")
            url = parts[1].decode('utf-8', errors='replace')
        except (IndexError, ValueError) as parse_err:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{thread_id}] Proxy Error: Malformed request dari {client_addr[0]}: {parse_err}")
            error_body = b"<html><body><h1>400 Bad Request</h1></body></html>"
            header = "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n"
            header += f"Content-Length: {len(error_body)}\r\n\r\n"
            client_socket.sendall(header.encode() + error_body)
            return

        # ── Normalisasi path ─────────────────────────────────────────
        path = url
        if path.startswith("http://") or path.startswith("https://"):
            parts_url = path.split("/", 3)
            path = "/" + parts_url[3] if len(parts_url) > 3 else "/index.html"

        if path == '/':
            path = '/index.html'

        cache_filename = path.replace("/", "_") + ".cache"
        cache_filepath = os.path.join(CACHE_DIR, cache_filename)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Cek cache ────────────────────────────────────────────────
        with cache_lock:
            has_cache = os.path.exists(cache_filepath)
            cached_response = None
            if has_cache:
                try:
                    with open(cache_filepath, 'rb') as f:
                        cached_response = f.read()
                except IOError as io_err:
                    print(f"[{timestamp}] [{thread_id}] Cache read error: {io_err}")
                    has_cache = False

        if cached_response is not None:
            try:
                client_socket.sendall(cached_response)
            except (BrokenPipeError, ConnectionResetError) as send_err:
                print(f"[{timestamp}] [{thread_id}] Client disconnected during cache send: {send_err}")
                return
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"[{timestamp}] [{thread_id}] Proxy: {client_addr[0]} -> {url} | Cache HIT ({elapsed_ms:.2f} ms)")

        else:
            # ── Forward ke Server ────────────────────────────────────
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(5.0)

            try:
                server_socket.connect((SERVER_HOST, SERVER_PORT))
                server_socket.sendall(request)

                response = b""
                while True:
                    data = server_socket.recv(4096)
                    if not data:
                        break
                    response += data

                # Simpan ke cache hanya jika 200 OK
                if b"200 OK" in response:
                    with cache_lock:
                        try:
                            with open(cache_filepath, 'wb') as f:
                                f.write(response)
                        except IOError as io_err:
                            print(f"[{timestamp}] [{thread_id}] Cache write error: {io_err}")

                # Kirim ke client
                try:
                    client_socket.sendall(response)
                except (BrokenPipeError, ConnectionResetError) as send_err:
                    print(f"[{timestamp}] [{thread_id}] Client disconnected during forward send: {send_err}")
                    return

                elapsed_ms = (time.time() - start_time) * 1000
                print(f"[{timestamp}] [{thread_id}] Proxy: {client_addr[0]} -> {url} | Cache MISS ({elapsed_ms:.2f} ms)")

            except socket.timeout:
                print(f"[{timestamp}] [{thread_id}] Proxy Error: Timeout dari origin server")
                _send_error(client_socket, 504,
                    "Gateway Timeout", "The origin server timed out.")

            except (ConnectionRefusedError, ConnectionResetError) as se:
                print(f"[{timestamp}] [{thread_id}] Proxy Error: Tidak dapat terhubung ke server: {se}")
                _send_error(client_socket, 502,
                    "Bad Gateway", f"Origin server unreachable: {se}")

            except socket.error as se:
                print(f"[{timestamp}] [{thread_id}] Proxy Socket Error: {se}")
                _send_error(client_socket, 503,
                    "Service Unavailable", f"Socket error: {se}")

            finally:
                server_socket.close()

    except socket.timeout:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{thread_id}] Proxy Error: Timeout membaca request dari client {client_addr[0]}")

    except Exception as e:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{thread_id}] Proxy Unexpected Error: {e}")

    finally:
        try:
            client_socket.close()
        except Exception:
            pass


def _send_error(sock, code, status, message):
    """Helper: kirim HTTP error response ke client."""
    body = f"<html><body><h1>{code} {status}</h1><p>{message}</p></body></html>".encode()
    header = f"HTTP/1.1 {code} {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
    header += f"Content-Length: {len(body)}\r\n\r\n"
    try:
        sock.sendall(header.encode() + body)
    except Exception:
        pass  # Client mungkin sudah disconnect
```

### Tabel Error yang Ditangani

| Kondisi | Kode HTTP | Keterangan |
|---------|-----------|------------|
| Request tidak valid (malformed) | `400 Bad Request` | Header HTTP tidak terbaca |
| Server tidak bisa dihubungi | `502 Bad Gateway` | `ConnectionRefusedError` |
| Server tidak merespons | `504 Gateway Timeout` | `socket.timeout` |
| Error socket umum | `503 Service Unavailable` | `socket.error` lainnya |
| Cache tidak bisa dibaca/ditulis | Log warning, lanjut | `IOError` |
| Client disconnect tiba-tiba | Log warning, hentikan | `BrokenPipeError` |

---

## 6. Log QoS Disimpan ke File CSV (`client.py`)

### Masalah Sebelumnya
Hasil QoS hanya dicetak ke terminal dan tidak tersimpan. Dokumen (Bagian F, hal. 13–14) mensyaratkan data RTT, packet loss, jitter, dan throughput dalam bentuk tabel/grafik. Tanpa penyimpanan, data tidak bisa digunakan untuk laporan.

### Revisi `client.py` – Fungsi `udp_pinger` dengan Export CSV

Tambahkan `import csv` dan `import os` di bagian atas file, lalu modifikasi `udp_pinger`:

```python
import csv
import os

CSV_LOG_PATH = "qos_log.csv"

def udp_pinger():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(1.0)

    rtt_list = []
    packets_sent = 10
    packets_lost = 0
    total_bytes_received = 0

    # ── Header CSV (buat file baru jika belum ada) ────────────────
    write_header = not os.path.exists(CSV_LOG_PATH)
    csv_rows = []   # Kumpulkan dulu, tulis setelah selesai

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

            rtt = (recv_time - send_time) * 1000
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
        time.sleep(0.1)

    test_end = time.time()
    duration = test_end - test_start

    # ── Kalkulasi statistik ───────────────────────────────────────
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
            print(f"Jitter (σ selisih RTT): {jitter:.2f} ms")
        else:
            print("Jitter: N/A (terlalu sedikit paket)")
    else:
        print("RTT: N/A (semua paket hilang)")

    loss_pct = (packets_lost / packets_sent) * 100
    total_bits = total_bytes_received * 8
    throughput = (total_bits / 1000.0) / duration if duration > 0 else 0.0

    print(f"Packet Loss: {loss_pct:.2f}%")
    print(f"Throughput : {throughput:.4f} kbps")

    # ── Tulis ke CSV ──────────────────────────────────────────────
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

    print(f"\n[✓] Log QoS disimpan ke: {CSV_LOG_PATH}")
    client.close()
```

### Contoh Output CSV

```
session_start,seq,status,rtt_ms,bytes_received
2025-06-14 10:00:01,1,received,1.2345,25
2025-06-14 10:00:01,2,received,1.1023,25
2025-06-14 10:00:01,3,timeout,,
...
2025-06-14 10:00:03,SUMMARY,"loss=10.00% jitter=0.45ms throughput=0.1823kbps","min=1.10 avg=1.25 max=2.30",225
```

> **Import tambahan yang diperlukan di `client.py`:**
> ```python
> import csv
> import os
> import datetime
> ```

---

## Checklist Verifikasi Setelah Revisi

Gunakan checklist ini sebelum pengumpulan:

- [ ] `webserver.py`: Log TCP mencantumkan nama thread (`TCP-<ip>-<port>`)
- [ ] `webserver.py`: UDP echo berjalan di thread terpisah, port `9090`
- [ ] `proxy.py`: Log setiap request mencantumkan nama thread (`Proxy-<ip>-<port>`)
- [ ] `proxy.py`: Error `400`, `502`, `503`, `504` terkirim dengan benar
- [ ] `proxy.py`: `BrokenPipeError` dan `IOError` pada cache tidak menyebabkan crash
- [ ] `client.py`: Menu interaktif tampil saat dijalankan tanpa argumen
- [ ] `client.py`: Argumen CLI (`--mode tcp/udp`) tetap berfungsi
- [ ] `client.py`: File `qos_log.csv` dibuat setelah UDP pinger selesai
- [ ] Browser diarahkan ke `http://127.0.0.1:8080` (Proxy), bukan `8000`
- [ ] Port UDP konsisten `9090` di semua file
- [ ] Tidak ada file Python tambahan (hanya `client.py`, `proxy.py`, `webserver.py`)

---

## Referensi Dokumen

Revisi ini mengacu pada **Jaringan Komputer – Modul 8** (Laboratorium Praktikum Informatika, Universitas Telkom), khususnya:

- Bagian E – Ketentuan Implementasi (hal. 8–10)
- Bagian F – Skenario Pengujian dan Analisis QoS (hal. 10–14)
- Bagian G – Laporan Akhir (hal. 16–17)
