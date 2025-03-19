import socket
import threading
import json

# Server configuration
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5555

clients = []
clients_lock = threading.Lock()

def broadcast(message, sender_conn):
    """Send the message to all clients except the sender."""
    with clients_lock:
        for client in clients:
            if client != sender_conn:
                try:
                    client.sendall(message)
                except Exception as e:
                    print(f"Broadcast error: {e}")
                    clients.remove(client)

def handle_client(conn, addr):
    """Receive messages from a client and broadcast them."""
    print(f"New connection from {addr}")
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break  # Connection closed
            # For clarity, we print the JSON message from the client.
            print(f"Received from {addr}: {data.decode()}")
            broadcast(data, conn)
        except Exception as e:
            print(f"Error with {addr}: {e}")
            break
    with clients_lock:
        if conn in clients:
            clients.remove(conn)
    conn.close()
    print(f"Connection with {addr} closed.")

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        with clients_lock:
            clients.append(conn)
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()

if __name__ == '__main__':
    main()
