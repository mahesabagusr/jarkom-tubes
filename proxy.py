import socket
import threading
import os
import datetime
import time

PROXY_PORT = 8080
PROXY_HOST = '127.0.0.1'
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000
SERVER_UDP_PORT = 9090
CACHE_DIR = "proxy_cache"

# Lock untuk sinkronisasi akses cache agar thread-safe tanpa race condition
cache_lock = threading.Lock()

# Buat folder cache jika belum ada
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)


def _send_error(sock, code, status, message):
    """Helper: kirim HTTP error response ke client."""
    body = f"<html><body><h1>{code} {status}</h1><p>{message}</p></body></html>".encode()
    header = f"HTTP/1.1 {code} {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
    header += f"Content-Length: {len(body)}\r\n\r\n"
    try:
        sock.sendall(header.encode() + body)
    except Exception:
        pass  # Client mungkin sudah disconnect


def handle_client(client_socket, client_addr):
    thread_id = threading.current_thread().name
    start_time = time.time()

    try:
        client_socket.settimeout(10.0)  # Timeout baca dari client
        request = client_socket.recv(4096)

        if not request:
            return

        # Parsing request
        try:
            first_line = request.split(b'\r\n')[0]
            parts = first_line.split(b' ')
            if len(parts) < 2:
                raise ValueError("Malformed HTTP request line")
            url = parts[1].decode('utf-8', errors='replace')
        except (IndexError, ValueError) as parse_err:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{thread_id}] Proxy Error: Malformed request dari {client_addr[0]}: {parse_err}")
            _send_error(client_socket, 400, "Bad Request", "Malformed HTTP request.")
            return

        # Normalisasi path
        path = url
        if path.startswith("http://") or path.startswith("https://"):
            parts_url = path.split("/", 3)
            path = "/" + parts_url[3] if len(parts_url) > 3 else "/index.html"

        if path == '/':
            path = '/index.html'

        cache_filename = path.replace("/", "_") + ".cache"
        cache_filepath = os.path.join(CACHE_DIR, cache_filename)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Cek cache
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
            # Forward ke Server
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
                _send_error(client_socket, 504, "Gateway Timeout", "The origin server timed out.")

            except (ConnectionRefusedError, ConnectionResetError) as se:
                print(f"[{timestamp}] [{thread_id}] Proxy Error: Tidak dapat terhubung ke server: {se}")
                _send_error(client_socket, 502, "Bad Gateway", f"Origin server unreachable: {se}")

            except socket.error as se:
                print(f"[{timestamp}] [{thread_id}] Proxy Socket Error: {se}")
                _send_error(client_socket, 503, "Service Unavailable", f"Socket error: {se}")

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
            name=f"Proxy-{addr[0]}-{addr[1]}"
        )
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    start_proxy()
