import socket
import threading
import os
import datetime

PROXY_PORT = 8080
PROXY_HOST = '127.0.0.1'
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000
CACHE_DIR = "proxy_cache"

# Buat folder cache jika belum ada
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def handle_client(client_socket, client_addr):
    try:
        request = client_socket.recv(4096)
        if not request:
            client_socket.close()
            return
            
        first_line = request.split(b'\r\n')[0]
        url = first_line.split(b' ')[1].decode('utf-8')
        if url == '/':
            url = '/index.html'
            
        cache_filename = url.replace("/", "_") + ".cache"
        cache_filepath = os.path.join(CACHE_DIR, cache_filename)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Cek apakah ada di cache
        if os.path.exists(cache_filepath):
            print(f"[{timestamp}] Proxy: {client_addr[0]} requested {url} - Cache HIT")
            with open(cache_filepath, 'rb') as f:
                response = f.read()
            client_socket.sendall(response)
        else:
            print(f"[{timestamp}] Proxy: {client_addr[0]} requested {url} - Cache MISS")
            
            # Forward ke Server
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(5.0) # Timeout untuk 504
            
            try:
                server_socket.connect((SERVER_HOST, SERVER_PORT))
                server_socket.sendall(request)
                
                response = b""
                while True:
                    data = server_socket.recv(4096)
                    if len(data) > 0:
                        response += data
                    else:
                        break
                
                # Simpan ke cache jika HTTP response OK (200)
                if b"200 OK" in response:
                    with open(cache_filepath, 'wb') as f:
                        f.write(response)
                
                # Kirim ke client
                client_socket.sendall(response)
                
            finally:
                server_socket.close()

    except Exception as e:
        print(f"Proxy Error: {e}")
    finally:
        client_socket.close()

def start_proxy():
    proxy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_server.bind((PROXY_HOST, PROXY_PORT))
    proxy_server.listen(10)
    print(f"[*] Proxy Server listening on {PROXY_HOST}:{PROXY_PORT}")
    
    while True:
        client_sock, addr = proxy_server.accept()
        thread = threading.Thread(target=handle_client, args=(client_sock, addr))
        thread.start()

if __name__ == "__main__":
    start_proxy()