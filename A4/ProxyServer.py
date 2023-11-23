from socket import *
import sys
import os

# Verifica si se proporciona el número correcto de argumentos de línea de comandos
if len(sys.argv) <= 1:
    print('Uso: "python ProxyServer.py server_ip"\n[server_ip : Es la dirección IP del servidor proxy')
    sys.exit(2)

# Crea un socket de servidor, lo vincula a un puerto y comienza a escuchar
tcpSerSock = socket(AF_INET, SOCK_STREAM)

# Vincula el socket a una dirección y puerto específicos
tcpSerSock.bind((sys.argv[1], 8888))

# Escucha las conexiones entrantes
tcpSerSock.listen(5)

while True:
    # Comienza a recibir datos del cliente
    print('Listo para servir...')
    tcpCliSock, addr = tcpSerSock.accept()
    print('Se ha recibido una conexión desde:', addr)
    
    # Recibe el mensaje del cliente
    message = tcpCliSock.recv(4096).decode()
    print(message)

    # Extrae el nombre de archivo del mensaje dado por el cliente
    print(message.split()[1])
    filename = message.split()[1].partition("/")[2]
    print(filename)
    fileExist = "false"
    filetouse = "/" + filename
    print(filetouse)

    try:
        # Verifica si el archivo existe en la caché
        f = open(filetouse[1:], "rb")
        outputdata = f.read()
        fileExist = "true"
        # El servidor proxy encuentra un resultado en la caché y genera un mensaje de respuesta
        tcpCliSock.send(b"HTTP/1.0 200 OK\r\n")
        tcpCliSock.send(b"Content-Type:text/html\r\n")
        tcpCliSock.send(b"\r\n")
        tcpCliSock.send(outputdata)
        print('Leído desde la caché')

    # Manejo de errores para archivos no encontrados en la caché
    except IOError:
        if fileExist == "false":
            # Crea un socket en el servidor proxy
            c = socket(AF_INET, SOCK_STREAM)
            hostn = filename.replace("www.", "", 1)
            print(hostn)

            try:
                # Conéctate al socket al puerto 80
                c.connect((hostn, 80))
                # Crea un archivo temporal en este socket y solicita el puerto 80
                # para el archivo solicitado por el cliente
                fileobj = c.makefile('r', 0)
                fileobj.write(f"GET /{filename} HTTP/1.0\r\nHost: {hostn}\r\n\r\n")

                # Lee la respuesta en un búfer
                buffer = fileobj.read()

                # Crea un nuevo archivo en la caché para el archivo solicitado.
                # También envía la respuesta en el búfer al socket del cliente
                # y el archivo correspondiente en la caché
                tmpFile = open("./" + filename, "wb")
                tmpFile.write(buffer)

                tcpCliSock.send(buffer)
            except:
                print("Solicitud no válida")

        else:
            # Mensaje de respuesta HTTP para archivo no encontrado
            response = "HTTP/1.0 404 Not Found\r\n\r\n"
            tcpCliSock.send(response.encode())

    # Cierra los sockets del cliente y del servidor
    tcpCliSock.close()
    c.close()
