import socket
from time import sleep


# HOST = socket.gethostname()  # Make socket visible to outside world
# HOST = "localhost"  # or "127.0.0.1" visible only within same machine
HOST = ""  # Symbolic name meaning all available interfaces
PORT = 54321  # Arbitrary non-privileged port

if __name__ == "__main__":
    # Create an INET, STREAMing socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serv_sock:
        # Bind the socket to a public host, and a port client knows
        serv_sock.bind((HOST, PORT))
        # Become a server socket
        # The argument means that only 1 connect request can wait to be accepted,
        # all other will be refused. So, if you run 2 clients: the 1st will be
        # accepted, the 2nd - waiting, and the 3rd - refused. The normal value is 5.
        serv_sock.listen(1)
        print("Server started")
        print("Waiting for connection...")
        sock, addr = serv_sock.accept()
        with sock:
            print("Connected by", addr)
            while True:
                # Receive
                data = sock.recv(1024)
                print(f"Received: {data} from: {addr}")
                if not data:
                    break
                # Process
                if data == b"close":
                    break
                data = data.upper()
                # Send
                print(f"Send: {data} to: {addr}")
                sock.sendall(data)

                sleep(5)

                data = b'another one'
                sock.sendall(data)
                print('send another one')
            print("Disconnected by", addr)
            # sock.close()  # No need as wrapped with "with sock:"
