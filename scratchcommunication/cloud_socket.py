"""
Handle cloud sockets.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
import warnings
import sys
from threading import Lock
from threading import Event as ThreadingEvent
from typing import Union, Any, Self, Literal, Optional
from weakref import proxy
import random, time
from itertools import islice
from .exceptions import NotSupported
from .cloud import CloudConnection, Context, Event
from . import security as sec

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
        
class BaseCloudSocketMSG(ABC):
    """
    Base class for cloud socket messages.
    """
    message : str
    @abstractmethod
    def add(self, data : str):
        """
        Add data to the message.
        """
    
    @abstractmethod
    def finalize(self, decode : bool = True):
        """
        Finalize the message.
        """
        
    @abstractmethod
    def __bool__(self) -> bool:
        pass
        
class BaseCloudSocketClient(ABC):
    """
    Base class for connecting with cloud sockets
    """
    @abstractmethod
    def __init__(self, *, cloud : CloudConnection, username : str = "user1000", packet_size : int = 220, security : Optional[Union[tuple, sec.Security]] = None):
        pass

    @abstractmethod
    def __enter__(self) -> Self:
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    @abstractmethod
    def _decode(data : int):
        """
        Decodes data sent from the server
        """

    @staticmethod
    @abstractmethod
    def _encode(data : str):
        """
        Encodes data for a client
        """

    @abstractmethod
    def connect(self):
        """
        Connect to the server
        """

    @abstractmethod
    def recv(self, timeout : Union[None, float] = 10):
        """
        Receive data from the server
        """

    @abstractmethod
    def send(self, data : str):
        """
        Send data to the server
        """
        
class AnyCloudSocket(ABC):
    """
    Base Class for cloud sockets
    """
    security : Union[None, sec.ConnectSecurity]
    cloud : CloudConnection
    clients : dict[str, BaseCloudSocketConnection]
    new_clients : list
    connecting_clients : list
    key_parts : dict
    last_timestamp : float
    packet_size : Union[int, Literal["AUTO"]]
    accepting : Lock
    accepted : ThreadingEvent
    received_any : ThreadingEvent
    any_update : ThreadingEvent
    
    @abstractmethod
    def __init__(self, *, cloud : CloudConnection, packet_size : Union[int, Literal["AUTO"]] = "AUTO", security : Union[None, tuple, sec.Security] = None):
        pass

    @abstractmethod
    def __enter__(self) -> Self:
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    @abstractmethod
    def accept(self, timeout : Union[float, int, None] = 10) -> tuple[Any, str]:
        """
        Returns a new client
        """
        
    @abstractmethod
    def listen(self) -> Self:
        """
        Start the cloud socket.
        """
        
    @abstractmethod
    def stop(self, cascade_stop : bool = True):
        """
        Stop the cloud socket.
        """
        
    @abstractmethod
    def send_to_client(self, *, data : str, client_id : str):
        """
        Send data to a client
        """
        
    @abstractmethod
    def secure_send_to_client(self, data : str, client : BaseCloudSocketConnection):
        """
        Use for sending data to the client if secure
        """
    
    @abstractmethod
    def recv_from_client(self, *, timeout : Union[float, int, None] = 10, client_id : str):
        """
        Receive data from a client
        """

class VariableCloudSocket(AnyCloudSocket):
    """
    Base Class for creating cloud sockets with projects
    """

    @staticmethod
    @abstractmethod
    def _decode(data : Union[int, str]) -> str:
        """
        Decodes data sent from a client
        """
    
    @staticmethod
    @abstractmethod
    def _encode(data : str) -> Union[str, int]:
        """
        Encodes data for a client
        """
    
    @abstractmethod
    def get_packet_size(self, client : BaseCloudSocketConnection):
        """
        Get the packet size for a client.
        """
    
BaseCloudSocket = VariableCloudSocket

class BaseCloudSocketConnection(Context, ABC):
    """
    Base Class for handling incoming connections from a cloud socket
    """
    cloud_socket : AnyCloudSocket
    client_id : str
    username : Optional[str]
    security : Optional[str]
    encrypter : Optional[sec.SymmetricEncryption]
    secure : bool
    new_msgs : list
    current_msg : BaseCloudSocketMSG
    receiving : Lock
    received : ThreadingEvent
    sending : Lock
    event : Event
    is_turbowarp : bool
    
    @abstractmethod
    def __init__(self, *, cloud_socket : AnyCloudSocket, client_id : str, username : Optional[str] = None, security : Optional[str] = None):
        pass
    
    @abstractmethod
    def __enter__(self) -> Self:
        pass
    
    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def recv(self, timeout : Union[float, int, None] = 10) -> str:
        """
        Use for sending data to the client
        """
        return self.cloud_socket.recv_from_client(timeout=timeout, client_id=self.client_id)

    def send(self, data : str):
        """
        Use for receiving data from the client
        """
        return self.cloud_socket.send_to_client(data=data, client_id=self.client_id)
        
    @abstractmethod
    def _new_msg(self):
        """
        Don't use.
        """

class CloudSocket(VariableCloudSocket):
    """
    Class for creating cloud sockets with projects
    """
    def __init__(self, *, cloud : CloudConnection, packet_size : Union[int, Literal["AUTO"]] = "AUTO", security : Union[None, tuple[int, int, int], sec.Security] = None):
        self.security = None
        security_type = None
        security_data : Optional[Union[tuple[int, int, int], tuple[str, str, str]]] = None
        if isinstance(security, tuple):
            security_type = "RSA"
            security_data = security
        elif isinstance(security, sec.Security):
            security_type = security.security_type
            security_data = security.data
        if security_type == "RSA":
            assert isinstance(security_data, tuple) and isinstance(security_data[0], int)
            self.security = sec.RSAKeys(security_data)
            warnings.warn("Switch to EC Security for much better performance!", UserWarning)
        if security_type == "EC":
            assert isinstance(security_data, tuple) and isinstance(security_data[0], str)
            self.security = sec.ECSecurity(security_data)
        self.cloud = cloud
        self.clients = {}
        self.new_clients = []
        self.connecting_clients = []
        self.key_parts : dict[str, str] = {}
        self.last_timestamp = time.time()
        self.packet_size = packet_size
        self.accepting = Lock()
        self.accepted = ThreadingEvent()
        self.received_any = ThreadingEvent()
        self.any_update = ThreadingEvent()
        
    def listen(self) -> Self:
        """
        Start the cloud socket.
        """
        @self.cloud.on("set")
        def on_packet(event : Event):
            try:
                assert event.type == "set"
                assert event.name == "FROM_CLIENT"
                salt = 0.0
                event_value = str(event.value)
                value = event_value.replace("-", "")
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
                    assert not "-" in event_value
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
                    affected_client = self.clients[client]
                    assert affected_client.encrypter is not None
                    self.last_timestamp = salt
                    affected_client.current_msg.add(decoded := affected_client.encrypter.decrypt(self._decode(msg_data[:-15]), int(msg_data[-15:])))
                    affected_client.event = event
                    event.emit("secure_message_part", client=self.clients[client], decoded=decoded, raw=msg_data)
                    assert not "-" in event_value
                    affected_client.current_msg.finalize(decode=False)
                    event.emit("secure_message", client=self.clients[client], content=self.clients[client].current_msg.message)
                    affected_client.new_msgs.append(self.clients[client].current_msg)
                    affected_client._new_msg()
                    affected_client.current_msg = CloudSocketMSG()
                    return
                
                # New secure user
                
                key = None
                if self._decode(msg_data[:28]).startswith("_safe_connect:"):
                    assert self.security
                    salt = int(msg_data[-15:]) / 100
                    assert salt > self.last_timestamp, "Invalid salt(too little)"
                    assert salt < time.time() + 30, "Invalid salt(too big)"
                    self.last_timestamp = salt
                    try:
                        key_parts = [self.key_parts["".join(key_part)] for key_part in batched(msg_data[28:-15], 5)]
                    except KeyError:
                        raise AssertionError from None
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
                    security=(key is not None or key) and str(key),
                    context=event
                )
                self.clients[client] = client_obj
                event.emit("new_user", client=client_obj)
                if client_obj.secure:
                    event.emit("new_secure_user", client=client_obj)
                self.new_clients.append((client_obj, client_username))
                self.accepted.set()
                self.any_update.set()
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
            decoded_key = self._decode(key[15:])
            decrypted_key = self.security.decrypt(decoded_key)
            unhexed_key = "".join(str(i) for i in bytes.fromhex(decrypted_key))
            integer_key = int(unhexed_key + str(salt))
            return integer_key
        elif isinstance(self.security, sec.RSAKeys):
            return self.security.decrypt(int(key))
        else:
            raise ValueError
            
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
    def _decode(data : Union[str, int]) -> str:
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
    def _encode(data : str) -> Union[str, int]:
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
    
    def accept(self, timeout : Union[float, int, None] = 10) -> tuple[BaseCloudSocketConnection, str]:
        """
        Returns a new client
        """
        endtime = (time.time() + timeout) if timeout is not None else None
        result = self.accepting.acquire(timeout=timeout if timeout is not None else -1)
        if not result:
            raise TimeoutError("The timeout expired (consider setting timeout=None)")
        try:
            while (not self.new_clients) and (endtime is None or time.time() < endtime):
                self.accepted.clear()
                self.accepted.wait(endtime and endtime - time.time())
            try:
                new_client = self.new_clients.pop(0)
                return new_client
            except IndexError:
                raise TimeoutError("The timeout expired (consider setting timeout=None)") from None
        finally:
            self.accepting.release()
                
    def send_to_client(self, *, data: str, client_id: str):
        client = self.clients[client_id]
        with client.sending:
            if client.secure:
                self.secure_send_to_client(data, client=client)
                return
            data = str(self._encode(data))
            packets = ["".join(i) for i in batched(data, self.get_packet_size(client=client))]
            packet_idx = 0
            var = 1
            for packet in packets[:-1]:
                client.set_var(
                    name=f"TO_CLIENT_{var}",
                    value=int(f"-{packet}.{client_id}{random.randrange(1000):03}{packet_idx}")
                )
                var = var % 4 + 1
                packet_idx += 1
            client.set_var(
                name=f"TO_CLIENT_{random.randint(1, 4)}",
                value=int(f"{packets[-1]}.{client_id}{random.randrange(1000):03}{packet_idx}")
            )

    def secure_send_to_client(self, data: str, client: BaseCloudSocketConnection):
        assert client.encrypter is not None
        packets = ["".join(i) for i in batched(data, self.get_packet_size(client=client) // 2 - 28)]
        packet_idx = 0
        var = 1
        for packet in packets[:-1]:
            salt = int(time.time() * 100)
            encoded_packet = self._encode(client.encrypter.encrypt(packet, salt=salt))
            client.set_var(
                name=f"TO_CLIENT_{var}",
                value=int(f"-{encoded_packet}{str(salt).zfill(15)}.{client.client_id}{random.randrange(1000):03}{packet_idx}")
            )
            var = var % 4 + 1
            packet_idx += 1
        salt = int(time.time() * 100)
        encoded_packet = self._encode(client.encrypter.encrypt(packets[-1], salt=salt))
        client.set_var(
            name=f"TO_CLIENT_{random.randint(1, 4)}",
            value=int(f"{encoded_packet}{str(salt).zfill(15)}.{client.client_id}{random.randrange(1000):03}{packet_idx}")
        )

    def recv_from_client(self, *, timeout: float | int | None = 10, client_id: str):
        client = self.clients[client_id]
        endtime = timeout and (time.time() + timeout)
        result = client.receiving.acquire(timeout=timeout if timeout is not None else -1)
        if not result:
            raise TimeoutError("The timeout expired (consider setting timeout=None)")
        try:
            while (not client.new_msgs) and (endtime is None or time.time() < endtime):
                client.received.wait(endtime and endtime - time.time())
            try:
                return client.new_msgs.pop(0).message
            except IndexError:
                raise TimeoutError("The timeout expired (consider setting timeout=None)") from None
        finally:
            client.receiving.release()
    
class CloudSocketConnection(BaseCloudSocketConnection):
    """
    Class for handling incoming connections from a cloud socket
    """
    def __init__(self, *, cloud_socket : AnyCloudSocket, client_id : str, username : Optional[str] = None, security : Optional[str] = None, context : Context):
        self.cloud_socket = cloud_socket
        self.client_id = client_id
        self.username = username
        self.security = security
        self.encrypter = (self.security is not None or self.security) and sec.SymmetricEncryption(int(self.security))
        self.secure = bool(self.security)
        self.new_msgs = []
        self.current_msg = CloudSocketMSG()
        self.receiving = Lock()
        self.sending = Lock()
        self.received = ThreadingEvent()
        self._cloud = context._cloud
        self.is_turbowarp = self._cloud.is_turbowarp
        self.event = proxy(context)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
            
    def _new_msg(self):
        """
        Don't use.
        """
        self.received.set()
        self.cloud_socket.received_any.set()
        self.cloud_socket.any_update.set()
    
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