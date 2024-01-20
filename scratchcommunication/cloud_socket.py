from .cloud import CloudConnection
from . import security as sec
from typing import Union, Any
import random, time, traceback
from itertools import islice
from .exceptions import ErrorInCloudSocket, NotSupported

alphabet = "abcdefghijklmnopqrstuvwxyz"
special_characters = " .,-:;_'#!\"§$%&/()=?{[]}\\0123456789<>ß*"
chars = alphabet + alphabet.upper() + special_characters
char_to_idx = {char: str(idx) if len(str(idx)) > 1 else "0" + str(idx) for idx, char in enumerate(chars, 1)}

def batched(iterable, n):
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch
        
class CloudSocketClient:
    """
    Class for connecting with cloud sockets
    """
    pass

class BaseCloudSocket:
    """
    Base Class for creating cloud sockets with projects
    """
    def __init__(self, *, cloud : CloudConnection, packet_size : int = 220, security : Union[None, tuple] = None):
        raise NotSupported

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    def _decode(data : int):
        """
        Decodes data sent from a client
        """
        pass
    
    @staticmethod
    def _encode(data : str):
        """
        Encodes data for a client
        """
        pass
    
    def accept(self) -> tuple[Any, str]:
        """
        Returns a new client
        """
        pass

class BaseCloudSocketConnection:
    """
    Base Class for handling incoming connections from a cloud socket
    """
    def __init__(self, *, cloud_socket : BaseCloudSocket, client_id : str, username : str = None, security : str = None):
        raise NotSupported
    
    def __enter__(self):
        pass
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def recv(self) -> str:
        """
        Use for sending data to the client
        """
        pass
    
    def send(self, data : str):
        """
        Use for receiving data from the client
        """
        pass

class CloudSocket(BaseCloudSocket):
    """
    Class for creating cloud sockets with projects
    """
    def __init__(self, *, cloud : CloudConnection, packet_size : int = 220, security : Union[None, tuple] = None):
        self.security = None if security is None else sec.RSAKeys(security)
        self.cloud = cloud
        self.clients = {}
        self.new_clients = []
        self.connecting_clients = []
        self.key_parts = {}
        self.last_timestamp = time.time()
        self.packet_size = packet_size
        @self.cloud.on("set")
        def on_packet(event):
            try:
                assert event.name == "FROM_CLIENT"
                salt = 0
                value = event.value.replace("-", "")
                msg_data = value.split(".", 1)[0]
                msg_type = int(value[0])
                
                # Key fragment
                
                if msg_type == 0:
                    key_part_id = msg_data[1:6]
                    assert not key_part_id in self.key_parts
                    key_part = msg_data[6:]
                    self.key_parts[key_part_id] = key_part
                    if len(self.key_parts) >= 100:
                        for key_part_id in list(self.key_parts.keys())[:-100]:
                            self.key_parts.pop(key_part_id)
                    return
                            
                # Non secure message part
                
                if (client := value.split(".", 1)[1][:5]) in self.clients and not self.clients[client].secure:
                    self.clients[client].current_msg.add(msg_data)
                    assert not "-" in event.value
                    self.clients[client].current_msg.finalize()
                    self.clients[client].new_msgs.append(self.clients[client].current_msg)
                    self.clients[client].current_msg = CloudSocketMSG()
                    return
                
                # Secure message part
                
                if client in self.clients and self.clients[client].secure:
                    salt = int(msg_data[-15:]) / 100
                    assert salt > self.last_timestamp, "Invalid salt(too little)"
                    assert salt < time.time() + 30, "Invalid salt(too big)"
                    self.last_timestamp = salt
                    self.clients[client].current_msg.add(" "+self.clients[client].encrypter.decrypt(self._decode(msg_data[1:-15]), msg_data[-15:]))
                    assert not "-" in event.value
                    self.clients[client].current_msg.finalize(decode=False)
                    self.clients[client].new_msgs.append(self.clients[client].current_msg)
                    self.clients[client].current_msg = CloudSocketMSG()
                    return
                
                # New secure user
                
                key = None
                if self._decode(msg_data[1:29]).startswith("_safe_connect:"):
                    assert self.security
                    salt = int(msg_data[-15:]) / 100
                    assert salt > self.last_timestamp, "Invalid salt(too little)"
                    assert salt < time.time() + 30, "Invalid salt(too big)"
                    self.last_timestamp = salt
                    key_parts = [self.key_parts.get("".join(key_part)) for key_part in batched(msg_data[29:-15], 5)]
                    assert not None in key_parts
                    c_key = int("".join(key_parts))
                    key = self.security.decrypt(c_key)
                    assert str(key).startswith(str(int(msg_data[-15:])))
                    
                # New user
                    
                client_username = None # Not currently supported
                client_obj = CloudSocketConnection(cloud_socket=self, client_id=client, username=client_username, security=key)
                self.clients[client] = client_obj
                self.new_clients.append((client_obj, client_username))
                return
            except AssertionError:
                pass

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    def _decode(data : int):
        """
        Decodes data sent from a client
        """
        data = str(data)
        decoded = ""
        for char_pair in zip(data[::2], data[1::2]):
            char_idx = int(char_pair[0] + char_pair[1]) - 1
            decoded += chars[char_idx]
        return decoded
    
    @staticmethod
    def _encode(data : str):
        """
        Encodes data for a client
        """
        encoded = "1"
        for char in data:
            encoded += char_to_idx[char]
        return int(encoded)
    
    def accept(self) -> tuple[BaseCloudSocketConnection, str]:
        """
        Returns a new client
        """
        while not self.new_clients: pass
        new_client = self.new_clients.pop(0)
        return new_client
    
class CloudSocketConnection(BaseCloudSocketConnection):
    """
    Class for handling incoming connections from a cloud socket
    """
    def __init__(self, *, cloud_socket : BaseCloudSocket, client_id : str, username : str = None, security : str = None):
        self.cloud_socket = cloud_socket
        self.client_id = client_id
        self.username = username
        self.security = security
        self.encrypter = sec.SymmetricEncryption(self.security)
        self.secure = bool(self.security)
        self.new_msgs = []
        self.current_msg = CloudSocketMSG()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def _secure_send(self, data : str):
        """
        Use for sending data to the client if secure
        """
        packets = ["".join(i) for i in batched(data, self.cloud_socket.packet_size // 2 - 15)]
        packet_idx = 0
        for packet in packets[:-1]:
            salt = int(time.time() * 100)
            packet = self.cloud_socket._encode(self.encrypter.encrypt(packet, salt=salt))
            self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"-{packet}{str(salt).zfill(15)}.{self.client_id}{packet_idx}")
            packet_idx += 1
        salt = int(time.time() * 100)
        packet = self.cloud_socket._encode(self.encrypter.encrypt(packets[-1], salt=salt))
        self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"{packet}{str(salt).zfill(15)}.{self.client_id}{packet_idx}")
    
    def send(self, data : str):
        """
        Use for sending data to the client
        """
        if self.secure:
            self._secure_send(data)
            return
        data = str(self.cloud_socket._encode(data))
        packets = list(batched(data, self.cloud_socket.packet_size))
        packet_idx = 0
        for packet in packets[:-1]:
            self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"-{packet}.{self.client_id}{packet_idx}")
            packet_idx += 1
        self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"{packets[-1]}.{self.client_id}{packet_idx}")

    def recv(self) -> str:
        """
        Use for receiving data from the client
        """
        while not self.new_msgs: pass
        return self.new_msgs.pop(0).message
    
class CloudSocketMSG:
    def __init__(self, message : str = "", complete : bool = False):
        self.message = message
        self.complete = complete
        
    def add(self, data):
        self.message += data[1:]
    
    def finalize(self, decode : bool = True):
        if decode:
            self.message = CloudSocket._decode(self.message)
        self.complete = True
        
    def __bool__(self):
        return self.complete