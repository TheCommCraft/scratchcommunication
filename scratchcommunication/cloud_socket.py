from .cloud import CloudConnection
import random

alphabet = "abcdefghijklmnopqrstuvwxyz"
special_characters = " .,-:;_'#!\"§$%&/()=?{[]}\\0123456789<>ß*"
chars = alphabet + alphabet.upper() + special_characters
char_to_idx = {char: str(idx) if len(str(idx)) > 1 else "0" + str(idx) for idx, char in enumerate(chars, 1)}

class CloudSocketClient:
    pass

class CloudSocket:
    def __init__(self, *, cloud : CloudConnection, packet_size : int = 220):
        self.cloud = cloud
        self.clients = {}
        self.new_clients = []
        self.new_msgs = {}
        self.packet_size = packet_size
        @self.cloud.on("set")
        def on_packet(event):
            if event.name != "FROM_CLIENT":
                return
            value = event.value.replace("-", "")
            if (client := value.split(".", 1)[1][:5]) in self.clients:
                self.clients[client] += value.split(".", 1)[0]
                if float(event.value) < 0:
                    return
                self.new_msgs[client].append(self._decode(self.clients[client]))
                self.clients[client] = ""
                return
            self.clients[client] = ""
            self.new_msgs[client] = []
            self.new_clients.append((client, event.user))

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @staticmethod
    def _decode(data : int):
        """
        Decodes data sent from a client
        """
        data = str(data)[1:]
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
    
    def accept(self):
        """
        Returns a new client
        """
        while not self.new_clients: pass
        new_client = self.new_clients.pop(0)
        return (CloudSocketConnection(cloud_socket=self, client_id=new_client[0], username=new_client[1]), new_client[1])
    
class CloudSocketConnection:
    def __init__(self, *, cloud_socket : CloudSocket, client_id : str, username : str = None):
        self.cloud_socket = cloud_socket
        self.client_id = client_id
        self.username = username

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass
    
    def send(self, data : str):
        """
        Use for sending data to the client
        """
        data = str(self.cloud_socket._encode(data))
        packets = [data[idx:idx + self.cloud_socket.packet_size] for idx in range(0, len(data), self.cloud_socket.packet_size)]
        packet_idx = 0
        for packet in packets[:-1]:
            self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"-{packet}.{self.client_id}{packet_idx}")
            packet_idx += 1
        self.cloud_socket.cloud.set_variable(name=f"TO_CLIENT_{random.randint(1, 4)}", value=f"{packets[-1]}.{self.client_id}{packet_idx}")

    def recv(self) -> str:
        """
        Use for receiving data from the client
        """
        while not self.cloud_socket.new_msgs[self.client_id]: pass
        return self.cloud_socket.new_msgs[self.client_id].pop(0)