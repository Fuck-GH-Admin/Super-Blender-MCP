"""Minimal TCP echo server for Blender - paste in Blender's text editor and run."""
import socket
import threading
import sys

def handle_client(conn, addr):
    print(f"[Echo] Client from {addr}")
    sys.stdout.flush()
    try:
        data = conn.recv(8192)
        print(f"[Echo] Got {len(data)} bytes: {data[:100]}")
        sys.stdout.flush()
        response = '{"status":"ok","result":{"test":"echo works"}}\n'
        conn.sendall(response.encode())
        print(f"[Echo] Response sent")
        sys.stdout.flush()
    except Exception as e:
        print(f"[Echo] Error: {e}")
        sys.stdout.flush()
    finally:
        conn.close()

def run_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 9877))
    sock.listen(1)
    sock.settimeout(1.0)
    print("[Echo] Listening on 0.0.0.0:9877")
    sys.stdout.flush()
    running = True
    while running:
        try:
            conn, addr = sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr))
            t.daemon = True
            t.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[Echo] Error: {e}")
            sys.stdout.flush()
    sock.close()

# Run in background thread
t = threading.Thread(target=run_server)
t.daemon = True
t.start()
print("[Echo] Server thread started on port 9877")
sys.stdout.flush()
