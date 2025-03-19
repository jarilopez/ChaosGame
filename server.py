import socket
import threading
import json
import time

SERVER_IP = '192.168.33.68'
SERVER_PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of address
server.bind((SERVER_IP, SERVER_PORT))
server.listen()

players = {}
player_ids = {}
next_id = 1
clients = []  # Keep track of all client connections

def broadcast(message):
    """Send data to all connected clients"""
    disconnected = []
    for client in clients:
        try:
            client.send(message)
        except:
            disconnected.append(client)
    
    # Remove disconnected clients
    for client in disconnected:
        if client in clients:
            clients.remove(client)

def handle_client(conn, addr):
    global next_id
    player_id = next_id
    next_id += 1
    player_ids[addr] = player_id
    clients.append(conn)
    
    print(f"New connection from {addr}, assigned ID: {player_id}")
    last_received = time.time()
    buffer = ""
    
    # Set socket timeout
    conn.settimeout(1.0)  # 1 second timeout for socket operations
    
    while True:
        try:
            data = conn.recv(4096)
            if not data:
                print(f"No data received from {addr}")
                break
                
            last_received = time.time()
            try:
                buffer += data.decode()
                player_data = json.loads(buffer)
                buffer = ""
                players[player_id] = player_data
                
                # Send acknowledgment back to client
                try:
                    response = json.dumps({"status": "ok", "players": players})
                    conn.send(response.encode())
                except:
                    print(f"Failed to send response to {addr}")
                    break
                
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Data error from {addr}: {e}")
                continue
            
        except socket.timeout:
            # Check if client is still active
            if time.time() - last_received > 10:  # Increased timeout to 10 seconds
                print(f"Client {addr} inactive for too long")
                break
            continue
            
        except ConnectionError as e:
            print(f"Connection lost with {addr}: {e}")
            break
            
        except Exception as e:
            print(f"Unexpected error with {addr}: {e}")
            break
    
    cleanup_client(conn, addr, player_id)

def cleanup_client(conn, addr, player_id):
    if conn in clients:
        clients.remove(conn)
    if player_id in players:
        del players[player_id]
    if addr in player_ids:
        del player_ids[addr]
    try:
        conn.close()
    except:
        pass
    # Notify remaining clients about player disconnect
    response = json.dumps(players)
    broadcast(response.encode())

print(f"Server started on {SERVER_IP}:{SERVER_PORT}, waiting for connections...")
while True:
    try:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
    except Exception as e:
        print(f"Error accepting connection: {e}")
        time.sleep(1)  # Prevent CPU spike on repeated errors
