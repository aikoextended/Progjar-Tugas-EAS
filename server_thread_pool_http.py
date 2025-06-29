from socket import *
import socket
import logging
from concurrent.futures import ThreadPoolExecutor
from http_server import HttpServer

httpserver = HttpServer()

def ProcessTheClient(connection, address):
    rcv = ""
    while True:
        try:
            data = connection.recv(1024)
            if data:
                d = data.decode('utf-8', 'ignore')
                rcv += d
                if '\r\n\r\n' in rcv:
                    lines = rcv.split('\r\n')
                    content_length = 0
                    for line in lines:
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':')[1].strip())
                            break
                    
                    header_end = rcv.find('\r\n\r\n')
                    body_received = len(rcv) - (header_end + 4)

                    if body_received >= content_length:
                        hasil = httpserver.proses(rcv)
                        connection.sendall(hasil)
                        connection.close()
                        return
            else:
                break
        except Exception as e:
            # logging.error(f"Error processing client {address}: {e}")
            break
    connection.close()


def Server():
    the_clients = []
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    my_socket.bind(('0.0.0.0', 8080))
    my_socket.listen(5)
    print("Checkers HTTP server started on port 8080")

    with ThreadPoolExecutor(20) as executor:
        while True:
            connection, client_address = my_socket.accept()
            executor.submit(ProcessTheClient, connection, client_address)

def main():
    Server()

if __name__ == "__main__":
    main()
