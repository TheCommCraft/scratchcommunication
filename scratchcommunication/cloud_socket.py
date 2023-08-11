from .cloud import CloudConnection
from .exceptions import ContextError
import random, math

alphabet = "abcdefghijklmnopqrstuvwxyz"
special_characters = " .,-:;_'#!\"§$%&/()=?{[]}\\0123456789<>ß*"
chars = alphabet + alphabet.upper() + special_characters
char_to_idx = {char: str(idx) if len(str(idx)) > 1 else "0" + str(idx) for idx, char in enumerate(chars, 1)}

class CloudSocketClient:
    '''
    Class for a client for a cloud socket
    '''

class CloudSocket:
    '''
    Class for a cloud socket.
    '''
    def __init__(self, *, cloud : CloudConnection, packet_size = 220, rsa_keys : tuple[int, int, int] = None):
        self.cloud = cloud
        self.clients = {}
        self.new_clients = []
        self.new_msgs = {}
        self.packet_size = packet_size
        self.secure = rsa_keys is not None
        self.rsa_keys = rsa_keys
        @self.cloud.on("set")
        def on_packet(event):
            if event.name != "FROM_CLIENT":
                return
            value = event.value.replace("-", "")
            if (client := value.split(".", 1)[1][:5]) in self.clients:
                self.clients[client]["data"] += value.split(".", 1)[0][1:]
                self.clients[client]["message_type"] = int(value[0])
                if float(event.value) < 0:
                    return
                match self.clients[client]["message_type"]:
                    case 1:
                        if self.clients[client]["session"] is not None:
                            return
                        self.new_msgs[client].append(self._decode(self.clients[client]["data"]))
                    case 2:
                        if self.clients[client]["session"] is None:
                            return
                        self.new_msgs[client].append(self._decode(self.clients[client]["data"]))
                self.clients[client]["data"] = ""
                return
            self.clients[client] = {"data": "", "message_type": 0, "new_msgs": [], "session": None}
            self.new_msgs[client] = []
            self.new_clients.append(client)
            if not self.secure:
                return
            if value.startwith("2"):
                self.clients[client]["session"] = pow(int(value[1:]), *self.rsa_keys[1:])

    @staticmethod
    def _decrypt(encrypted, key) -> str:
        '''
        Decrypt messages from client.
        '''
        seed = int(encrypted[1:int(encrypted[0]) + 1])
        subkey = 66666
        for i in str(key):
            i = int(i)
            subkey *= subkey
            subkey += i
            subkey %= 33*seed
        shift = pow(431, 21, subkey)
        decrypted = ""
        _expshift = ""
        tolog = f"\n{encrypted[int(encrypted[0]) + 1:]} ->"
        expshift = None
        for i in encrypted[int(encrypted[0]) + 1:]:
            i = chars[(char_to_idx[i] - shift) % 89]
            if i == ":":
                derypted += _expshift
                expshift = f":{shift}"
                _expshift = ":"
            else:
                _expshift += i
            #print(shift, i)
            tolog += str(shift) + " "
            shift = (shift * 431) % subkey
        tolog += f"->{decrypted}{_expshift}{expshift}"
        #log(tolog)
        if expshift != _expshift:
            raise ValueError("Bad Token")
        return decrypted

    @staticmethod
    def _encrypt(text, key):
        '''
        Encrypt messages for the client.
        '''
        seed = random.randrange(71232, 131572)
        subkey = 66666
        for i in str(key):
            i = int(i)
            subkey *= subkey
            subkey += i
            subkey %= 33*seed
        shift = pow(431, 21, subkey)
        token = f"{len(str(seed))}{seed}"
        for i in text:
            token += chars[(char_to_idx[i] + shift) % 89]
            #print(shift)
            shift = (shift * 431) % subkey
        for i in f":{shift}":
            token += chars[(char_to_idx[i] + shift) % 89]
            #print(shift)
            shift = (shift * 431) % subkey
        return token


    def generate_rsa_keys(self):
        '''
        Activates security for an unsecure cloud socket and return the new rsa keys as a tuple.
        '''
        self.rsa_keys = self._decode_tuple(self.create_rsa_keys())
        self.secure = True
        return self.rsa_keys

    def get_rsa_keys(self):
        '''
        Return the current rsa keys in a format that the project can understand.
        '''
        try:
            return self._encode_tuple(self.rsa_keys)
        except TypeError:
            raise ContextError("No rsa keys") from None

    @classmethod
    def create_rsa_keys(cls):
        '''
        Creates rsa keys in a format that the project can understand.
        '''
        rsa_keys = None
        public_exponent = 3
        lower_limit = 1 << 500
        upper_limit = 1 << 750
        while True:
            p, q = (cls._create_random_prime(lower_limit, upper_limit), cls._create_random_prime(lower_limit, upper_limit))
            n = p * q
            a = (p - 1) * (q - 1)
            if math.gcd(public_exponent, a) != 1:
                continue
            e = public_exponent
            for d in range(1 + a, 1 + 1000000 * a, a):
                if d % e == 0:
                    d //= e
                    break
            else:
                continue
            rsa_keys = e, d, n
            break
        return cls._encode_tuple(rsa_keys)
    
    @classmethod
    def _create_random_prime(cls, lower, upper):
        while True:
            if cls._is_prime(prime := random.randrange(lower, upper)):
                return prime

    @staticmethod
    def _is_prime(n, t=100):
        if n <= 1:
            return False
        if n <= 3:
            return True
        if n % 2 == 0:
            return False
        m = (n - 1) // 2
        j = 1
        while not m % 2:
            j += 1
            m = m // 2
        d = m
        for _ in range(t):
            a = random.randrange(2, n - 2)
            x = pow(a, d, n)
            if x == 1 or x == n - 1:
                continue
            for _ in range(j - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False
        return True

    @staticmethod
    def _decode_tuple(data : str):
        return tuple(int(i) for i in data.split("&"))
    
    @staticmethod
    def _encode_tuple(data : tuple):
        return "&".join(str(i) for i in data)

    @staticmethod
    def _decode(data : int):
        '''
        Decodes data sent from a client.
        '''
        data = str(data)[1:]
        decoded = ""
        for char_pair in zip(data[::2], data[1::2]):
            char_idx = int(char_pair[0] + char_pair[1]) - 1
            decoded += chars[char_idx]
        return decoded
    
    @staticmethod
    def _encode(data : str):
        '''
        Encodes data for a client.
        '''
        encoded = "1"
        for char in data:
            encoded += char_to_idx[char]
        return int(encoded)
    
    def accept(self):
        '''
        Returns a new client.
        '''
        while not self.new_clients: pass
        return CloudSocketConnection(cloud_socket=self, client_id=self.new_clients.pop(0))
    
class CloudSocketConnection:
    '''
    A client from a cloud socket
    '''
    def __init__(self, *, cloud_socket : CloudSocket, client_id : str):
        self.cloud_socket = cloud_socket
        self.client_id = client_id
    
    def send(self, data : str):
        '''
        Use for sending data to the client.
        '''
        data = str(self.cloud_socket._encode(data))
        packets = [data[idx:idx + self.cloud_socket.packet_size] for idx in range(0, len(data), self.cloud_socket.packet_size)]
        for packet in packets[:-1]:
            self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"-{packet}.{self.client_id}{random.randrange(100000)}")
        self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"{packets[-1]}.{self.client_id}{random.randrange(100000)}")

    def recv(self) -> str:
        '''
        Use for receiving data from the client.
        '''
        while not self.cloud_socket.new_msgs[self.client_id]: pass
        return self.cloud_socket.new_msgs[self.client_id].pop(0)