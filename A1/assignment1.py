import socket
import os

def handle_request(client_socket):
    request = client_socket.recv(1024)
    request_lines = request.split(b"\r\n")
    filename = request_lines[0].split()[1]
    if filename == b"/":
        filename = b"/index.html"
    try:
        with open(os.path.join(".", filename), "rb") as f:
            content = f.read()
            response = b"HTTP/1.1 200 OK\r\n"
            response += b"Content-Type: text/html\r\n"
            response += b"Content-Length: %d\r\n" % len(content)
            response += b"\r\n"
            response += content
    except FileNotFoundError:
        response = b"HTTP/1.1 404 Not Found\r\n"
        response += b"\r\n"
        response += b"404 Not Found"
    client_socket.sendall(response)
    client_socket.close()

def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("localhost", 6789))
    server_socket.listen(1)
    while True:
        client_socket, client_address = server_socket.accept()
        handle_request(client_socket)

if __name__ == "__main__":
    run_server()
