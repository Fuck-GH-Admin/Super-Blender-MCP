"""Diagnostic script - run in Blender's Python console to test the TCP server."""
import socket
import json
import threading

# Test 1: Check if port 9876 is listening
print("=" * 50)
print("Test 1: Check if port 9876 is available")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(('0.0.0.0', 9876))
    print("  Port 9876 is FREE - server is NOT running")
    sock.close()
except OSError as e:
    print(f"  Port 9876 is IN USE - server IS running: {e}")
    sock.close()

# Test 2: Try connecting to the server
print("\nTest 2: Connect to localhost:9876")
try:
    conn = socket.create_connection(('localhost', 9876), timeout=5)
    print("  Connected!")

    # Test 3: Send a command
    print("\nTest 3: Send get_scene_info command")
    cmd = json.dumps({"type": "get_scene_info", "params": {}}) + "\n"
    conn.sendall(cmd.encode("utf-8"))
    print("  Sent command, waiting for response...")

    conn.settimeout(10)
    data = b""
    while True:
        chunk = conn.recv(8192)
        if not chunk:
            break
        data += chunk
        if b"\n" in data:
            break

    if data:
        response = json.loads(data.decode("utf-8").strip())
        print(f"  Response status: {response.get('status')}")
        if response.get('status') == 'ok':
            result = response.get('result', {})
            print(f"  Objects in scene: {len(result.get('objects', []))}")
            print(f"  Camera: {result.get('camera')}")
        else:
            print(f"  Error: {response.get('message')}")
    else:
        print("  No response received!")
    conn.close()
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 50)
print("Done. If Test 3 shows 'No response', the addon has a timer issue.")
