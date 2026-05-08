import socket

ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ss.bind(('127.0.0.1', 12000))
ss.listen(1)
print("Server listening on port 12000...")

conn, addr = ss.accept()
print(f"Client connected from {addr}")

username = conn.recv(1024).decode('ascii')
print(f"Client name: {username}")

conn.sendall(f"Welcome {username}!".encode('ascii'))

conn.close()
ss.close()