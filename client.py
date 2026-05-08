import socket

HOST = '127.0.0.1'
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

client.sendall(b"Hello from client!")

response = client.recv(1024).decode()
print(f"Server says: {response}")

client.close()
