import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 12000))

client.sendall(b"Hello from client!")

response = client.recv(1024).decode()
print(f"Server says: {response}")

client.close()
