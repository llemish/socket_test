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
                        if int(value) > 1024:
                            value = 1024
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

        if len(data) > 3 and (':' in data or data[:2] == '*/'):
            self._is_correct = True

            if data[:2] == '*/':
                self._is_command = True
                if ':' in data:
                    self._target_user = data.split(':')[0].strip()[2:]
                    self._message = data.split(':')[1].strip()
                else:
                    self._target_user = data[2:].strip()
            else:
                self._target_user = data.split(':')[0].strip()
                self._message = data.split(':')[1].strip()


class Server:

    def __init__(self):
        self._config = ConfigReader('config')
        logg_level = self._get_logg_level()
        logging.basicConfig(level=logg_level, filename='syslog.log', filemode='a',
                            format="%(asctime)s:%(module)s:%(levelname)s:%(message)s")

        self._users = dict()
        self._sel = selectors.DefaultSelector()

        self._run_server()

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
            self._sel.register(server_sock, selectors.EVENT_READ, self._new_connection)
            while True:
                logging.debug("Waiting for connections or data...")
                events = self._sel.select()
                for key, mask in events:
                    callback = key.data
                    try:
                        success = callback(key.fileobj)
                        if not success:
                            self._delete_user(key.fileobj)
                    except OSError:
                        logging.warning(f'Client {key.fileobj} suddenly disconnected!')
                        sock = key.fileobj
                        self._sel.unregister(sock)
                        if sock in self._users:
                            del self._users[sock]

    def _new_connection(self, server_sock):
        sock, addr = server_sock.accept()
        if len(self._users) <= self._config.max_user:
            self._sel.register(sock, selectors.EVENT_READ, self._get_user_message)
            logging.debug(f'New connection from {addr}')
            new_user = User('noname')
            new_user.sock = sock
            self._users[new_user.sock] = new_user
        else:
            logging.info(f'Too many users, connection denied')
            sock.sendall('Достигнуто предельное количество пользователей!'.encode())
            sock.close()
        return True

    def _get_user_message(self, sock):
        addr = sock.getpeername()
        logging.debug(f'Get new message from {addr}')

        # Receive
        try:
            data = sock.recv(1024)
        except ConnectionError:
            logging.warning(f'Client {addr} suddenly closed')
            return False
        logging.debug(f'Recieved {data} from {addr}')

        # Handle message
        new_data = self._handle_message(data, sock)
        if not new_data:
            return False

        # Send
        success = self._send_message(sock, new_data)
        return success

    def _delete_user(self, sock):
        logging.info(f'Delete user from socket {sock}')
        del self._users[sock]
        self._sel.unregister(sock)

    def _get_user_names(self):
        names = [self._users[user].name for user in self._users]
        return names

    def _send_message(self, sock, data):
        if isinstance(data, str):
            data = data.encode()
        addr = sock.getpeername()
        logging.debug(f'Send {data} to {addr}')

        try:
            sock.sendall(data)
        except ConnectionError:
            logging.warning(f'Client {addr} suddenly closed')
            return False
        return True

    def _handle_message(self, data, sock):
        message = Message(data)

        if not message.is_correct:
            return 'Неверный формат сообщения или команды'.encode()

        if message.is_command:
            new_data = self._command_handler(message.target_user, message.message, sock)
        else:
            success = self._send_message_to_user(message.target_user, message.message, sock)
            if success:
                new_data = f'Сообщение отправлено {message.target_user}'
            else:
                new_data = f'Не удалось отправить сообщение {message.target_user}'
        return new_data.encode()

    def _command_handler(self, command, parameter, sock):
        new_data = f'Команда {command} не найдена'
        if command == 'init':
            new_data = str(self._config.max_message_length)
        elif command in ['registration', 'change_name']:
            name = parameter
            names = self._get_user_names()
            if name in names:
                new_data = 'Имя занято, выберите другое'
            else:
                self._users[sock].name = name
                new_data = f'Имя успешно сменено на {name}'
        elif command == 'who':
            names = self._get_user_names()
            new_data = f'Доступные пользователи: {names}'
        elif command == 'exit':
            new_data = 'Bye!'
            self._delete_user(sock)
        return new_data

    def _send_message_to_user(self, target_user, message, sock):

        target_socket = None
        for key in self._users:
            if self._users[key].name == target_user:
                target_socket = self._users[key].sock
                break
        if target_socket is None:
            return False

        message = f'Сообщение от {self._users[sock].name}: {message}'
        success = self._send_message(target_socket, message)

        return success

s = Server()
