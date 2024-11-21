import socket
from dataclasses import dataclass
import select
from time import sleep


@dataclass
class ClientInfo:

    HOST = '127.0.0.1'
    PORT = 54321
    MESSAGE_LENGTH = 140

class Client:

    def __init__(self):
        self._name = None
        self._max_message_length = ClientInfo.MESSAGE_LENGTH

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with self._sock:
            self._sock.connect((ClientInfo.HOST, ClientInfo.PORT))
            self._handshake()
            while True:
                self._handle_connection()

    def _handshake(self):
        self._send('*/hello')
        message = self._read()
        assert message == '*/connected'
        print('Подключение...')
        name = input('Введите имя: ')
        self._send(name)

    def _handle_connection(self):
        pass

    def _send(self, message):
        message_byte = message.encode()
        self._sock.sendall(message_byte)

    def _read(self):
        message_bytes = self._sock.recv(self._max_message_length)
        message = message_bytes.decode()
        return message


user = Client()
