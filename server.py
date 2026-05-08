import socket

HOST = '127.0.0.1'
PORT = 5000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)
print("Server listening on port 5000...")

conn, addr = server.accept()
print(f"Client connected from {addr}")

msg = conn.recv(1024).decode()
print(f"Received: {msg}")

conn.sendall(b"Hello from server!")
conn.close()
server.close()
