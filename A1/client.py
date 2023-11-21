import socket

# Define el servidor y el puerto al que te conectas
server_address = ('localhost', 8080)

# Crea un socket TCP/IP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Conéctate al servidor
client_socket.connect(server_address)

# Define la solicitud HTTP
request = "GET /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n"

# Envía la solicitud al servidor
client_socket.sendall(request.encode())

# Recibe y muestra la respuesta del servidor
response = b""
while True:
    data = client_socket.recv(1024)
    if not data:
        break
    response += data

print("Response from server:")
print(response.decode())

# Cierra el socket
client_socket.close()
