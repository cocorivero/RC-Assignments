from socket import *
import ssl
import base64

# Mensaje de prueba
msg = "\r\n ¡Amo las redes de computadoras!"
endmsg = "\r\n.\r\n"

# Elige un servidor de correo 
mailserver = ("smtp.gmail.com", 587)

# Crea un socket llamado clientSocket y establece una conexión TCP con mailserver
clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect(mailserver)

recv = clientSocket.recv(1024).decode()
print(recv)
if recv[:3] != '220':
    print('220 respuesta no recibida del servidor.')

# Envía el comando HELO y muestra la respuesta del servidor.
heloCommand = 'HELO Alice\r\n'
clientSocket.send(heloCommand.encode())
recv1 = clientSocket.recv(1024).decode()
print(recv1)
if recv1[:3] != '250':
    print('250 respuesta no recibida del servidor.')

# Envía el comando STARTTLS para iniciar una conexión segura
tlsCommand = 'STARTTLS\r\n'
clientSocket.send(tlsCommand.encode())
recv_tls = clientSocket.recv(1024).decode()
print(recv_tls)

# Mejora el socket a una conexión segura
context = ssl.create_default_context()
clientSocket = context.wrap_socket(clientSocket, server_hostname=mailserver[0])

# Autenticación
username = "riveroandy02@gmail.com"
password = "albj nkoi uzvs cusl"

# Envía el comando AUTH LOGIN y muestra la respuesta del servidor.
authCommand = 'AUTH LOGIN\r\n'
clientSocket.send(authCommand.encode())
recv_auth = clientSocket.recv(1024).decode()
print(recv_auth)

# Envía el nombre de usuario codificado en base64 y muestra la respuesta del servidor.
clientSocket.send(base64.b64encode(username.encode()) + b'\r\n')
recv_user = clientSocket.recv(1024).decode()
print(recv_user)

# Envía la contraseña codificada en base64 y muestra la respuesta del servidor.
clientSocket.send(base64.b64encode(password.encode()) + b'\r\n')
recv_pass = clientSocket.recv(1024).decode()
print(recv_pass)

# Envía el comando HELO nuevamente antes de enviar el correo
heloCommand = 'HELO smtp.gmail.com\r\n'
clientSocket.send(heloCommand.encode())
recv1 = clientSocket.recv(1024).decode()
print(recv1)

# Envía el comando MAIL FROM
mailFromCommand = 'MAIL FROM: <riveroandy02@gmail.com>\r\n'
clientSocket.send(mailFromCommand.encode())
recv2 = clientSocket.recv(1024).decode()
print(recv2)

# Envía el comando RCPT TO
rcptToCommand = 'RCPT TO: <andy.rivero@avangenio.com>\r\n'
clientSocket.send(rcptToCommand.encode())
recv3 = clientSocket.recv(1024).decode()
print(recv3)

# Envía el comando DATA y muestra la respuesta del servidor.
dataCommand = 'DATA\r\n'
clientSocket.send(dataCommand.encode())
recv4 = clientSocket.recv(1024).decode()
print(recv4)

# Envía los datos del mensaje.
clientSocket.send(msg.encode())

# El mensaje termina con un solo punto.
clientSocket.send(endmsg.encode())
recv5 = clientSocket.recv(1024).decode()
print(recv5)

# Envía el comando QUIT y obtén la respuesta del servidor.
quitCommand = 'QUIT\r\n'
clientSocket.send(quitCommand.encode())
recv6 = clientSocket.recv(1024).decode()
print(recv6)

# Cierra el socket
clientSocket.close()
