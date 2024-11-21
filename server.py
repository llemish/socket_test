import selectors
import socket
import logging


class ConfigReader:

    def __init__(self, path_to_file):
        self._port = 50001
        self._logging_level = 'DEBUG'
        self._max_user = 11
        self._max_message_length = 139
        self._read_file(path_to_file)

    def _read_file(self, path_to_file):
        with open(path_to_file) as f:
            for raw_line in f:
                if raw_line[0] != '#':
                    (key, value) = raw_line.split(':')
                    if key == 'LOGGING_LEVEL':
                        self._logging_level = value.rstrip()
                    elif key == 'PORT':
                        self._port = int(value)
                    elif key == 'MAX_MESSAGE_LENGTH':
                        self._max_message_length = int(value)
                    elif key == 'MAX_USER':
                        self._max_user = int(value)

    @property
    def port(self):
        return self._port

    @property
    def logging_level(self):
        return self._logging_level

    @property
    def max_user(self):
        return self._max_user

    @property
    def max_message_length(self):
        return self._max_message_length


class User:

    def __init__(self, name):
        self._name = name
        self._registered = False
        self._sock = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self._name = new_name
        self._registered = True

    @property
    def registered(self):
        return self._registered

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, sock):
        self._sock = sock


class Message:

    def __init__(self, raw_data):

        self._is_correct = False
        self._is_command = False
        self._message = ''
        self._target_user = None

        self._handle(raw_data)

    @property
    def is_correct(self):
        return self._is_correct

    @property
    def is_command(self):
        return self._is_command

    @property
    def message(self):
        return self._message

    @property
    def target_user(self):
        return self._target_user

    def _handle(self, raw_data):
        data = raw_data.strip().decode()

        if len(data) > 3 and (':' in data or data[:2] == '/*'):
            self._is_correct = True

            if data[:2] == '/*':
                self._is_command = True
                if ':' in data:
                    self._target_user = data.split(':')[0][2:]
                    self._message = data.split(':')[1]
                else:
                    self._target_user = data[2:]
            else:
                self._target_user = data.split(':')[0]
                self._message = data.split(':')[1]


class Server:

    def __init__(self):
        self._config = ConfigReader('config')
        logg_level = self._get_logg_level()
        logging.basicConfig(level=logg_level, filename='syslog.log', filemode='a',
                            format="%(asctime)s:%(module)s:%(levelname)s:%(message)s")
        self._users = dict()
        self._run_server()
        self._user_id = 0

    def _get_logg_level(self):
        level = logging.DEBUG
        if self._config.logging_level == 'INFO':
            level = logging.INFO
        elif self._config.logging_level == 'WARNING':
            level = logging.WARNING
        elif self._config.logging_level == 'ERROR':
            level = logging.ERROR
        elif self._config.logging_level == 'CRITICAL':
            level = logging.CRITICAL
        return level

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.bind(('', self._config.port))
            server_sock.listen(5)
            logging.debug('Server started')
            sel = selectors.DefaultSelector()
            sel.register(server_sock, selectors.EVENT_READ, self._new_connection)
            while True:
                logging.debug("Waiting for connections or data...")
                events = sel.select()
                for key, mask in events:
                    callback = key.data
                    callback(sel, key.fileobj, mask)

    def _new_connection(self, sel, server_sock, mask):
        sock, addr = server_sock.accept()
        if len(self._users) <= self._config.max_user:
            sel.register(sock, selectors.EVENT_READ, self._get_user_message)
            logging.debug(f'New connection from {addr}')
            new_user = User(self._user_id)
            self._user_id += 1
            new_user.sock = sock
            self._users[new_user.sock] = new_user
        else:
            logging.info(f'Too many users, connection denied')
            sock.send('Достигнуто предельное количество пользователей!'.encode())
            sock.close()

    def _get_user_message(self, sel, sock, mask):
        addr = sock.getpeername()
        logging.debug(f'Get new message from {addr}')

        # Receive
        try:
            data = sock.recv(self._config.max_message_length)
        except ConnectionError:
            logging.warning(f'Client {addr} suddenly closed')
            return False
        logging.debug(f'Recieved {data} from {addr}')

        # Handle message
        new_data = self._handle_message(data, sock)
        if not new_data:
            return False

        # Send
        self._send_message(sock, new_data)

        # logging.debug(f'Send {new_data} to {addr}')
        # try:
        #     if len(new_data) > self._config.max_message_length:
        #         pass
        #     else:
        #         sock.send(new_data)
        # except ConnectionError:
        #     logging.warning(f'Client {addr} suddenly closed')
        #     return False

    def _send_message(self, sock, data):
        addr = sock.getpeername()
        logging.debug(f'Send {data} to {addr}')

        try:
            if len(data) > self._config.max_message_length:
                pass
            else:
                sock.send(data)
        except ConnectionError:
            logging.warning(f'Client {addr} suddenly closed')
            return False
        return True

    def _handle_message(self, data, sock):
        message = Message(data)

        if not message.is_correct:
            return False

        if message.is_command:
            new_data = self._command_handler(message.target_user, message.message, sock)
        else:
            new_data = self._send_message_to_user(message.target_user, message.message, sock)
        return new_data

    def _command_handler(self, command, parameter, sock):
        new_data = False
        if command == 'init':
            new_data = str(self._config.max_message_length)
        elif command in ['registration', 'change_name']:
            name = parameter
            names = [user.name for user in self._users if user.name == name]
            if names == list():
                self._users[sock].name = name
                new_data = f'Имя успешно сменено на {name}'
            else:
                new_data = 'Имя занято, выберите другое'
        return new_data.encode()

    def _send_message_to_user(self, target_user, message, sock):

        target_socket = None
        for key in self._users:
            if self._users[key].name == target_user:
                target_socket = self._users[key].sock
                break
        if target_socket is None:
            return False

        message = self._users[sock].name + ':' + message
        success = self._send_message(target_socket, message)

        return success

s = Server()