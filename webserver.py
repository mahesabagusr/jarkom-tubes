import socket
import threading
import os
import datetime

# Konfigurasi Port
TCP_PORT = 8000
UDP_PORT = 9000
HOST = '127.0.0.1'

def handle_tcp_client(client_socket, client_address):
    try:
        request = client_socket.recv(1024).decode('utf-8')
        if not request:
            return

        # Parsing request (hanya GET)
        headers = request.split('\r\n')
        first_line = headers[0].split()
        if len(first_line) > 1 and first_line[0] == 'GET':
            path = first_line[1]
            if path == '/':
                path = '/index.html'
            
            filepath = '.' + path
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                # Membaca file
                with open(filepath, 'rb') as f:
                    content = f.read()
                
                # Membuat HTTP 200 OK Response
                response_header = "HTTP/1.1 200 OK\r\n"
                response_header += "Content-Type: text/html; charset=utf-8\r\n"
                response_header += f"Content-Length: {len(content)}\r\n\r\n"
                
                client_socket.sendall(response_header.encode('utf-8') + content)
                print(f"[{timestamp}] TCP: {client_address[0]} requested {path} - 200 OK")

            except FileNotFoundError:
                # Membuat HTTP 404 Response
                error_body = b"<html><body><h1>404 Not Found</h1></body></html>"
                response_header = "HTTP/1.1 404 Not Found\r\n"
                response_header += "Content-Type: text/html; charset=utf-8\r\n"
                response_header += f"Content-Length: {len(error_body)}\r\n\r\n"
                
                client_socket.sendall(response_header.encode('utf-8') + error_body)
                print(f"[{timestamp}] TCP: {client_address[0]} requested {path} - 404 Not Found")
                
    except Exception as e:
        print(f"Server Error: {e}")
    finally:
        client_socket.close()

def tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, TCP_PORT))
    server.listen(5)
    print(f"[*] Web Server (TCP) listening on {HOST}:{TCP_PORT}")
    
    while True:
        client_sock, addr = server.accept()
        client_thread = threading.Thread(target=handle_tcp_client, args=(client_sock, addr))
        client_thread.start()

def udp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, UDP_PORT))
    print(f"[*] Echo Server (UDP) listening on {HOST}:{UDP_PORT}")
    
    while True:
        data, addr = server.recvfrom(1024)
        # Pantulkan payload identik (echo)
        server.sendto(data, addr)

if __name__ == "__main__":
    t1 = threading.Thread(target=tcp_server)
    t2 = threading.Thread(target=udp_server)
    t1.start()
    t2.start()