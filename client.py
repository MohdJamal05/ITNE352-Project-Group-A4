import socket

server_add = ('127.0.0.1', 12000)

cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cs.connect(server_add)

username = input("Enter your name: ")
cs.sendall(username.encode('ascii'))

response = cs.recv(1024)
print("Server says:", response.decode('ascii'))

cs.close()