import socket
import threading
import json

SERVER_IP = '192.168.33.68'
SERVER_PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER_IP, SERVER_PORT))
server.listen()

players = {}
player_ids = {}
next_id = 1

def handle_client(conn, addr):
    global next_id
    player_id = next_id
    next_id += 1
    player_ids[addr] = player_id
    
    print(f"New connection from {addr}, assigned ID: {player_id}")
    
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
                
            player_data = json.loads(data.decode())
            players[player_id] = player_data
            
            # Send updated players data to all clients
            response = json.dumps(players)
            conn.send(response.encode())
            
        except:
            break
    
    print(f"Client {addr} disconnected")
    if player_id in players:
        del players[player_id]
    if addr in player_ids:
        del player_ids[addr]
    conn.close()

print("Server started, waiting for connections...")
while True:
    conn, addr = server.accept()
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()
