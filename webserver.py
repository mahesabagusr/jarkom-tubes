import socket
import threading
import os
import datetime
import mimetypes

# konfigurasi
TCP_PORT = 8000
UDP_PORT = 9090
HOST = '127.0.0.1'
ALLOWED_PROXY_IP = '127.0.0.1'

# Web root: semua file statis dilayani dari folder HTML/ (relatif terhadap
# lokasi webserver.py, jadi tidak tergantung current working directory).
WEB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HTML")

def handle_tcp_client(client_socket, client_address):
    thread_id = threading.current_thread().name
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Validasi: hanya terima koneksi dari IP Proxy
    if client_address[0] != ALLOWED_PROXY_IP:
        print(f"[{timestamp}] TCP Thread [{thread_id}]: DITOLAK - Koneksi langsung dari {client_address[0]} (bukan Proxy)")
        error_body = b"<html><body><h1>403 Forbidden</h1><p>Akses langsung tidak diizinkan. Gunakan Proxy.</p></body></html>"
        response_header = "HTTP/1.1 403 Forbidden\r\n"
        response_header += "Content-Type: text/html; charset=utf-8\r\n"
        response_header += f"Content-Length: {len(error_body)}\r\n\r\n"
        try:
            client_socket.sendall(response_header.encode('utf-8') + error_body)
        except Exception:
            pass
        client_socket.close()
        return

    print(f"[{timestamp}] TCP Thread [{thread_id}]: Handling connection from {client_address[0]}:{client_address[1]}")
    try:
        request = client_socket.recv(1024).decode('utf-8')
        if not request:
            return

        # Parsing request (hanya GET)
        headers = request.split('\r\n')
        first_line = headers[0].split()
        if len(first_line) > 1 and first_line[0] == 'GET':
            path = first_line[1]

            # Support absolute URLs (e.g., GET http://127.0.0.1:8080/index.html)
            if path.startswith("http://") or path.startswith("https://"):
                parts = path.split("/", 3)
                if len(parts) > 3:
                    path = "/" + parts[3]
                else:
                    path = "/index.html"

            # Buang query string (mis. /index.html?x=1 -> /index.html)
            if '?' in path:
                path = path.split('?', 1)[0]

            if path == '/':
                path = '/index.html'

            # Bangun path file di dalam WEB_ROOT secara aman.
            # normpath + lstrip mencegah directory traversal (mis. /../proxy.py).
            rel_path = os.path.normpath(path).lstrip("\\/")
            filepath = os.path.join(WEB_ROOT, rel_path)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Pastikan file final tetap berada di dalam WEB_ROOT
            if not os.path.abspath(filepath).startswith(os.path.abspath(WEB_ROOT)):
                error_body = b"<html><body><h1>403 Forbidden</h1><p>Path tidak diizinkan.</p></body></html>"
                response_header = "HTTP/1.1 403 Forbidden\r\n"
                response_header += "Content-Type: text/html; charset=utf-8\r\n"
                response_header += f"Content-Length: {len(error_body)}\r\n\r\n"
                client_socket.sendall(response_header.encode('utf-8') + error_body)
                print(f"[{timestamp}] TCP Thread [{thread_id}]: {client_address[0]} requested {path} - 403 Forbidden (traversal)")
                return

            try:
                # Membaca file (mode biner agar gambar/video/CSS utuh)
                with open(filepath, 'rb') as f:
                    content = f.read()

                # Tentukan Content-Type otomatis berdasarkan ekstensi file
                content_type, _ = mimetypes.guess_type(filepath)
                if content_type is None:
                    content_type = "application/octet-stream"
                # Tambahkan charset hanya untuk konten teks
                if content_type.startswith("text/") or content_type in (
                    "application/javascript", "application/json"
                ):
                    content_type += "; charset=utf-8"

                # Membuat HTTP 200 OK Response
                response_header = "HTTP/1.1 200 OK\r\n"
                response_header += f"Content-Type: {content_type}\r\n"
                response_header += f"Content-Length: {len(content)}\r\n\r\n"

                client_socket.sendall(response_header.encode('utf-8') + content)
                print(f"[{timestamp}] TCP Thread [{thread_id}]: {client_address[0]} requested {path} - 200 OK ({content_type})")

            except (FileNotFoundError, IsADirectoryError):
                # Coba sajikan halaman 404 custom dari HTML/status/404.html
                error_path = os.path.join(WEB_ROOT, "status", "404.html")
                try:
                    with open(error_path, 'rb') as f:
                        error_body = f.read()
                except (FileNotFoundError, IsADirectoryError):
                    error_body = b"<html><body><h1>404 Not Found</h1></body></html>"

                response_header = "HTTP/1.1 404 Not Found\r\n"
                response_header += "Content-Type: text/html; charset=utf-8\r\n"
                response_header += f"Content-Length: {len(error_body)}\r\n\r\n"

                client_socket.sendall(response_header.encode('utf-8') + error_body)
                print(f"[{timestamp}] TCP Thread [{thread_id}]: {client_address[0]} requested {path} - 404 Not Found")

    except Exception as e:
        print(f"[{thread_id}] Server Error: {e}")
    finally:
        client_socket.close()

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
            name=f"TCP-{addr[0]}-{addr[1]}"
        )
        client_thread.daemon = True
        client_thread.start()

def udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, UDP_PORT))
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
    print(f"[*] Server running on port {TCP_PORT} (TCP) / {UDP_PORT} (UDP), multithreading aktif")
    t1 = threading.Thread(target=tcp_server, name="TCPServer-Main")
    t2 = threading.Thread(target=udp_server, name="UDPServer-Main")
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()
    t1.join()
    t2.join()
