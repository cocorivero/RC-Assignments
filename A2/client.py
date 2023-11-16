import socket
import time

# Dirección del servidor y puerto
server_address = ('localhost', 12000)

# Número de pings a enviar
num_pings = 10

# Crear un socket UDP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Configurar un tiempo de espera en segundos
timeout = 1
client_socket.settimeout(timeout)

# Loop para enviar 10 pings
for i in range(1, num_pings + 1):
    # Mensaje ping a enviar
    message = f'Ping {i}'

    # Guardar el tiempo de inicio
    start_time = time.time()

    try:
        # Enviar el mensaje al servidor
        client_socket.sendto(message.encode(), server_address)

        # Recibir la respuesta del servidor
        response, server_address = client_socket.recvfrom(1024)

        # Calcular el tiempo de ida y vuelta (RTT)
        rtt = time.time() - start_time

        # Imprimir la respuesta y el RTT
        print(f'Respuesta desde {server_address}: {response.decode()} - RTT: {rtt:.6f} segundos')

    except socket.timeout:
        # Si ocurre un timeout, imprimir "Solicitud agotada"
        print(f'Ping {i}: Solicitud agotada')

# Cerrar el socket
client_socket.close()
