
import socket
import selectors
import sys
from time import sleep


HOST = "localhost"  # The remote host
PORT = 54321  # The same port as used by the server
IS_RECONNECT_ENABLED = False

def input_read(sock):
    data = input().encode()
    sock.sendall(data)

def get_message(sock):
    data = sock.recv(1024)
    data = data.decode()
    print('Received: ' + data)

if __name__ == "__main__":

    is_started = False
    while IS_RECONNECT_ENABLED or not is_started:
        is_started = True
        print()
        print("Create client")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:

            def on_input_read():
                data = input().encode()
                sock.sendall(data)


            def on_get_message():
                data = sock.recv(1024)
                data = data.decode()
                print('Received: ' + data)

            sock.connect((HOST, PORT))
            print("Client connected")
            sel = selectors.DefaultSelector()
            sel.register(sys.stdin, selectors.EVENT_READ, on_input_read)
            sel.register(sock, selectors.EVENT_READ, on_get_message)
            while True:
                events = sel.select()
                for key, mask in events:
                    callback = key.data
                    callback()

