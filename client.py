import socket
import time
import sys
import statistics

PROXY_HOST = '127.0.0.1'
PROXY_PORT = 8080
SERVER_HOST = '127.0.0.1'
SERVER_UDP_PORT = 9000

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

def udp_pinger():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(1.0) # Maksimal 1 detik timeout per paket
    
    rtt_list = []
    packets_sent = 10
    packets_lost = 0
    
    print(f"Mengirim {packets_sent} paket UDP ke {SERVER_HOST}:{SERVER_UDP_PORT}\n")
    
    for i in range(1, packets_sent + 1):
        send_time = time.time()
        message = f"Ping {i} {send_time}"
        
        try:
            client.sendto(message.encode('utf-8'), (SERVER_HOST, SERVER_UDP_PORT))
            data, server = client.recvfrom(1024)
            recv_time = time.time()
            
            rtt = (recv_time - send_time) * 1000 # dalam milisekon
            rtt_list.append(rtt)
            print(f"Paket {i}: Balasan diterima dari {server[0]}, RTT = {rtt:.2f} ms")
            
        except socket.timeout:
            print(f"Paket {i}: Request timed out")
            packets_lost += 1
            
    # Kalkulasi Statistik Akhir
    print("\n--- Statistik QoS Ping UDP ---")
    if len(rtt_list) > 0:
        print(f"RTT -> Min: {min(rtt_list):.2f} ms | Avg: {statistics.mean(rtt_list):.2f} ms | Max: {max(rtt_list):.2f} ms")
        
        # Kalkulasi Jitter (Standar deviasi perbedaan RTT berturut-turut)
        if len(rtt_list) > 1:
            diffs = [abs(rtt_list[j] - rtt_list[j-1]) for j in range(1, len(rtt_list))]
            jitter = statistics.mean(diffs)
            print(f"Jitter (Rata-rata deviasi berurutan): {jitter:.2f} ms")
        else:
            print("Jitter: N/A (Terlalu sedikit paket yang diterima)")
    else:
        print("RTT: N/A (Semua paket hilang)")
        
    loss_percentage = (packets_lost / packets_sent) * 100
    print(f"Packet Loss: {loss_percentage:.2f}%")
    client.close()

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "-mode":
        print("Penggunaan: python client.py -mode tcp ATAU python client.py -mode udp")
        sys.exit(1)
        
    mode = sys.argv[2].lower()
    
    if mode == "tcp":
        tcp_client()
    elif mode == "udp":
        udp_pinger()
    else:
        print("Mode tidak valid. Gunakan 'tcp' atau 'udp'.")