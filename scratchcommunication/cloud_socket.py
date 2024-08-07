from __future__ import annotations
from .cloud import CloudConnection, Context, Event
from . import security as sec
import warnings
import sys
from threading import Lock, Condition
from typing import Union, Any, Self, Literal
from weakref import proxy
import random, time
from itertools import islice
from .exceptions import NotSupported

sys.set_int_max_str_digits(99999)

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
        
class BaseCloudSocketMSG:
    """
    Base class for cloud socket messages.
    """
        
class BaseCloudSocketClient:
    """
    Base class for connecting with cloud sockets
    """
    def __init__(self, *, cloud : CloudConnection, username : str = "user1000", packet_size : int = 220, security : Union[None, tuple, sec.Security] = None):
        raise NotImplementedError
    
    def __enter__(self) -> Self:
        raise NotImplementedError
    
    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError
    
    @staticmethod
    def _decode(data : int):
        """
        Decodes data sent from the server
        """
        raise NotImplementedError
    
    @staticmethod
    def _encode(data : str):
        """
        Encodes data for a client
        """
        raise NotImplementedError
    
    def connect(self):
        """
        Connect to the server
        """
        raise NotImplementedError
    
    def recv(self, timeout : Union[None, float] = 10):
        """
        Receive data from the server
        """
        raise NotImplementedError
    
    def send(self, data : str):
        """
        Send data to the server
        """
        raise NotImplementedError

class BaseCloudSocket:
    """
    Base Class for creating cloud sockets with projects
    """
    security : Union[None, sec.ConnectSecurity]
    cloud : CloudConnection
    clients : dict[str, BaseCloudSocketConnection]
    new_clients : list
    connecting_clients : list
    key_parts : dict
    last_timestamp : float
    packet_size : int
    accepting : Lock
    accepted : Condition
    received_any : Condition
    any_update : Condition
    def __init__(self, *, cloud : CloudConnection, packet_size : Union[int, Literal["AUTO"]] = "AUTO", security : Union[None, tuple, sec.Security] = None):
        raise NotImplementedError

    def __enter__(self) -> Self:
        raise NotImplementedError
    
    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError

    @staticmethod
    def _decode(data : int) -> str:
        """
        Decodes data sent from a client
        """
        raise NotImplementedError
    
    @staticmethod
    def _encode(data : str):
        """
        Encodes data for a client
        """
        raise NotImplementedError
    
    def accept(self) -> tuple[Any, str]:
        """
        Returns a new client
        """
        raise NotImplementedError
    
    def get_packet_size(self, client : BaseCloudSocketConnection):
        """
        Get the packet size for a client.
        """
        raise NotImplementedError

class BaseCloudSocketConnection(Context):
    """
    Base Class for handling incoming connections from a cloud socket
    """
    cloud_socket : BaseCloudSocket
    client_id : str
    username : str
    security : str
    encrypter : sec.SymmetricEncryption
    secure : bool
    new_msgs : list
    current_msg : BaseCloudSocketMSG
    receiving : Lock
    received : Condition
    sending : Lock
    event : Event
    is_turbowarp : bool
    def __init__(self, *, cloud_socket : BaseCloudSocket, client_id : str, username : str = None, security : str = None):
        raise NotImplementedError
    
    def __enter__(self) -> Self:
        raise NotImplementedError
    
    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError
    
    def recv(self) -> str:
        """
        Use for sending data to the client
        """
        raise NotImplementedError
    
    def send(self, data : str):
        """
        Use for receiving data from the client
        """
        raise NotImplementedError

class CloudSocket(BaseCloudSocket):
    """
    Class for creating cloud sockets with projects
    """
    def __init__(self, *, cloud : CloudConnection, packet_size : Union[int, Literal["AUTO"]] = "AUTO", security : Union[None, tuple, sec.Security] = None):
        self.security = None
        security_type = None
        if isinstance(security, tuple):
            security_type = "RSA"
        if isinstance(security, sec.Security):
            security_type = security.security_type
            security = security.data
        if security_type == "RSA":
            self.security = sec.RSAKeys(security)
            warnings.warn("Switch to EC Security for much better performance!", UserWarning)
        if security_type == "EC":
            self.security = sec.ECSecurity(security)
        self.cloud = cloud
        self.clients = {}
        self.new_clients = []
        self.connecting_clients = []
        self.key_parts = {}
        self.last_timestamp = time.time()
        self.packet_size = packet_size
        self.accepting = Lock()
        self.accepted = Condition(Lock())
        self.received_any = Condition(Lock())
        self.any_update = Condition(Lock())
        
    def listen(self) -> Self:
        """
        Start the cloud socket.
        """
        @self.cloud.on("set")
        def on_packet(event : Event):
            try:
                assert event.type == "set"
                assert event.name == "FROM_CLIENT"
                salt = 0
                value = event.value.replace("-", "")
                msg_data = value.split(".", 1)[0][1:]
                msg_type = int(value[0])
                
                # Key fragment
                
                if msg_type == 0:
                    key_part_id = msg_data[:5]
                    assert not key_part_id in self.key_parts
                    key_part = msg_data[5:]
                    self.key_parts[key_part_id] = key_part
                    if len(self.key_parts) >= 100:
                        for key_part_id in list(self.key_parts.keys())[:-100]:
                            self.key_parts.pop(key_part_id)
                    return
                            
                # Non secure message part
                
                client = value.split(".", 1)[1][:5]
                
                if not (self._decode(msg_data[:28]).startswith("_connect") or self._decode(msg_data[:28]).startswith("_safe_connect:")) and client in self.clients and not self.clients[client].secure:
                    event.emit("non_secure_message_part", client=self.clients[client], decoded=self._decode(msg_data), raw=msg_data)
                    self.clients[client].current_msg.add(msg_data)
                    self.clients[client].event = event
                    assert not "-" in event.value
                    self.clients[client].current_msg.finalize()
                    event.emit("non_secure_message", client=self.clients[client], content=self.clients[client].current_msg.message)
                    self.clients[client].new_msgs.append(self.clients[client].current_msg)
                    self.clients[client]._new_msg()
                    self.clients[client].current_msg = CloudSocketMSG()
                    return
                
                # Secure message part
                
                if not (self._decode(msg_data[:28]).startswith("_connect") or self._decode(msg_data[:28]).startswith("_safe_connect:")) and client in self.clients and self.clients[client].secure:
                    salt = int(msg_data[-15:]) / 100
                    assert salt > self.last_timestamp, "Invalid salt(too little)"
                    assert salt < time.time() + 30, "Invalid salt(too big)"
                    self.last_timestamp = salt
                    self.clients[client].current_msg.add(self.clients[client].encrypter.decrypt(self._decode(msg_data[:-15]), msg_data[-15:]))
                    self.clients[client].event = event
                    event.emit("secure_message_part", client=self.clients[client], decoded=self.clients[client].encrypter.decrypt(self._decode(msg_data[:-15]), msg_data[-15:]), raw=msg_data)
                    assert not "-" in event.value
                    self.clients[client].current_msg.finalize(decode=False)
                    event.emit("secure_message", client=self.clients[client], content=self.clients[client].current_msg.message)
                    self.clients[client].new_msgs.append(self.clients[client].current_msg)
                    self.clients[client]._new_msg()
                    self.clients[client].current_msg = CloudSocketMSG()
                    return
                
                # New secure user
                
                key = None
                if self._decode(msg_data[:28]).startswith("_safe_connect:"):
                    assert self.security
                    salt = int(msg_data[-15:]) / 100
                    assert salt > self.last_timestamp, "Invalid salt(too little)"
                    assert salt < time.time() + 30, "Invalid salt(too big)"
                    self.last_timestamp = salt
                    key_parts = [self.key_parts.get("".join(key_part)) for key_part in batched(msg_data[28:-15], 5)]
                    assert not None in key_parts
                    c_key = "".join(key_parts)
                    key = self._decrypt_key(c_key)
                    assert str(key).endswith(str(int(msg_data[-15:]))) or str(key).startswith(str(int(msg_data[-15:])))
                    
                # New user
                    
                try:
                    client_username = event.user
                except NotSupported:
                    client_username = None
                client_obj = CloudSocketConnection(
                    cloud_socket=self,
                    client_id=client,
                    username=client_username,
                    security=key,
                    context=event
                )
                self.clients[client] = client_obj
                event.emit("new_user", client=client_obj)
                if client_obj.secure:
                    event.emit("new_secure_user", client=client_obj)
                self.new_clients.append((client_obj, client_username))
                with self.accepted:
                    self.accepted.notify_all()
                with self.any_update:
                    self.any_update.notify_all()
                return
            except AssertionError:
                pass
        return self
    
    def get_packet_size(self, client : BaseCloudSocketConnection):
        """
        Get the packet size for a client.
        """
        if self.packet_size != "AUTO":
            return self.packet_size
        if client.is_turbowarp:
            return 98800
        return 220
            
    def _decrypt_key(self, key : str) -> int:
        if isinstance(self.security, sec.ECSecurity):
            salt = int(key[:15])
            key = self._decode(key[15:])
            key = self.security.decrypt(key)
            key = "".join(str(i) for i in bytes.fromhex(key))
            key = int(key + str(salt))
            return key
        if isinstance(self.security, sec.RSAKeys):
            return self.security.decrypt(int(key))
            
    def stop(self, cascade_stop : bool = True):
        """
        Stop the cloud socket.
        """
        self.cloud.stop_thread(cascade_stop=cascade_stop)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    @staticmethod
    def _decode(data : str) -> str:
        """
        Decodes data sent from a client
        """
        data = str(data)
        decoded = ""
        for char_pair in zip(data[::2], data[1::2]):
            char_idx = int(char_pair[0] + char_pair[1]) - 1
            try:
                decoded += chars[char_idx]
            except IndexError:
                warnings.warn(f"There was an error in decoding a message: \"{data}\" has \"{char_idx}\" which doesn't exist.")
        return decoded
    
    @staticmethod
    def _encode(data : str) -> str:
        """
        Encodes data for a client
        """
        encoded = "1"
        for char in data:
            try:
                encoded += char_to_idx[char]
            except KeyError:
                encoded += char_to_idx["?"]
        return encoded
    
    def accept(self, timeout : Union[float, None] = 10) -> tuple[BaseCloudSocketConnection, str]:
        """
        Returns a new client
        """
        with self.accepted:
            endtime = (time.time() + timeout) if timeout is not None else None
            result = self.accepting.acquire(timeout=timeout if timeout is not None else -1)
            if not result:
                raise TimeoutError("The timeout expired (consider setting timeout=None)")
            try:
                while (not self.new_clients) and (timeout is None or time.time() < endtime): 
                    self.accepted.wait(timeout and endtime - time.time())
                try:
                    new_client = self.new_clients.pop(0)
                    return new_client
                except IndexError:
                    raise TimeoutError("The timeout expired (consider setting timeout=None)") from None
            finally:
                self.accepting.release()
    
class CloudSocketConnection(BaseCloudSocketConnection):
    """
    Class for handling incoming connections from a cloud socket
    """
    def __init__(self, *, cloud_socket : BaseCloudSocket, client_id : str, username : str = None, security : str = None, context : Context):
        self.cloud_socket = cloud_socket
        self.client_id = client_id
        self.username = username
        self.security = security
        self.encrypter = sec.SymmetricEncryption(self.security)
        self.secure = bool(self.security)
        self.new_msgs = []
        self.current_msg = CloudSocketMSG()
        self.receiving = Lock()
        self.sending = Lock()
        self.received = Condition(Lock())
        self._cloud = context._cloud
        self.is_turbowarp = self._cloud.is_turbowarp
        self.event = proxy(context)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def _secure_send(self, data : str):
        """
        Use for sending data to the client if secure
        """
        packets = ["".join(i) for i in batched(data, self.cloud_socket.get_packet_size(client=self) // 2 - 28)]
        packet_idx = 0
        var = 1
        for packet in packets[:-1]:
            salt = int(time.time() * 100)
            packet = self.cloud_socket._encode(self.encrypter.encrypt(packet, salt=salt))
            self.set_var(
                name=f"TO_CLIENT_{var}",
                value=f"-{packet}{str(salt).zfill(15)}.{self.client_id}{random.randrange(1000):03}{packet_idx}"
            )
            var = var % 4 + 1
            packet_idx += 1
        salt = int(time.time() * 100)
        packet = self.cloud_socket._encode(self.encrypter.encrypt(packets[-1], salt=salt))
        self.set_var(
            name=f"TO_CLIENT_{random.randint(1, 4)}",
            value=f"{packet}{str(salt).zfill(15)}.{self.client_id}{random.randrange(1000):03}{packet_idx}"
        )
    
    def send(self, data : str):
        """
        Use for sending data to the client
        """
        with self.sending:
            if self.secure:
                self._secure_send(data)
                return
            data = str(self.cloud_socket._encode(data))
            packets = ["".join(i) for i in batched(data, self.cloud_socket.get_packet_size(client=self))]
            packet_idx = 0
            var = 1
            for packet in packets[:-1]:
                self.set_var(
                    name=f"TO_CLIENT_{var}",
                    value=f"-{packet}.{self.client_id}{random.randrange(1000):03}{packet_idx}"
                )
                var = var % 4 + 1
                packet_idx += 1
            self.set_var(
                name=f"TO_CLIENT_{random.randint(1, 4)}",
                value=f"{packets[-1]}.{self.client_id}{random.randrange(1000):03}{packet_idx}"
            )

    def recv(self, timeout : Union[float, None] = 10) -> str:
        """
        Use for receiving data from the client
        timeout defaults to 10 (seconds) but can be set to None if you do not want timeout.
        """
        with self.received:
            endtime = (time.time() + timeout) if timeout is not None else None
            result = self.receiving.acquire(timeout=timeout if timeout is not None else -1)
            if not result:
                raise TimeoutError("The timeout expired (consider setting timeout=None)")
            try:
                while (not self.new_msgs) and (timeout is None or time.time() < endtime):
                    self.received.wait(timeout and endtime - time.time())
                try:
                    return self.new_msgs.pop(0).message
                except IndexError:
                    raise TimeoutError("The timeout expired (consider setting timeout=None)")
            finally:
                self.receiving.release()
            
    def _new_msg(self):
        """
        Don't use.
        """
        with self.received, self.cloud_socket.received_any, self.cloud_socket.any_update:
            self.received.notify_all()
            self.cloud_socket.received_any.notify_all()
            self.cloud_socket.any_update.notify_all()
    
class CloudSocketMSG(BaseCloudSocketMSG):
    """
    Class for cloud socket messages.
    """
    def __init__(self, message : str = "", complete : bool = False):
        self.message = message
        self.complete = complete
        
    def add(self, data):
        self.message += data
    
    def finalize(self, decode : bool = True):
        if decode:
            self.message = CloudSocket._decode(self.message)
        self.complete = True
        
    def __bool__(self):
        return self.complete