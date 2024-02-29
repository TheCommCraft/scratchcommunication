import warnings
from .headers import headers
from .exceptions import InvalidValueError, ErrorInCloudSocket
from . import cloud, cloud_socket
import requests, json, re

class Session:
    __slots__ = ("session_id", "username", "headers", "cookies", "xtoken", "email", "id", "permissions", "flags", "banned", "session_data", "mute_status", "new_scratcher")
    def __init__(self, username : str = None, *, session_id : str):
        self.session_id = session_id
        self.username = username
        self.headers = headers
        self.cookies = {
            "scratchcsrftoken" : "a",
            "scratchlanguage" : "en",
            "scratchpolicyseen": "true",
            "scratchsessionsid" : self.session_id,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        self._login()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def logout(self):
        for attr in self.__slots__:
            delattr(self, attr)

    def _login(self):
        '''
        Don't use this
        '''
        try:
            account = requests.post("https://scratch.mit.edu/session", headers=self.headers, cookies={
                "scratchsessionsid": self.session_id,
                "scratchcsrftoken": "a",
                "scratchlanguage": "en",
            }).json()
            self.xtoken = account["user"]["token"]
            self.username = account["user"]["username"]
            self.headers["X-Token"] = self.xtoken
            self.email = account["user"]["email"]
            self.id = account["user"]["id"]
            self.permissions = account["permissions"]
            self.flags = account["flags"]
            self.banned = account["user"]["banned"]
            self.session_data = account
            self.new_scratcher = account["permissions"]["new_scratcher"]
            self.mute_status = account["permissions"]["mute_status"]
        except Exception:
            if self.username is None:
                raise ValueError("No username supplied and there was no found. The username is needed.")
            warnings.warn("Couldn't find token. Most features will probably still work.")

    @classmethod
    def login(cls, username : str, password : str):
        '''
        Login from your username and password.
        '''
        try:
            return cls(
                username, session_id=str(re.search('"(.*)"', requests.post(
                    "https://scratch.mit.edu/login/",
                    data=json.dumps({
                        "username": username,
                        "password": password
                    }),
                    headers=headers,
                    cookies={
                        "scratchcsrftoken": "a",
                        "scratchlanguage": "en"
                    },
                    timeout=10
                ).headers["Set-Cookie"]).group())
            )
        except AttributeError:
            raise InvalidValueError("Your login was wrong")
        except Exception as e:
            raise Exception("An error occurred while trying to log in.") from e
        
    def create_cloudconnection(self, project_id : int, **kwargs) -> cloud.CloudConnection:
        '''
        Create a cloud connection to a project.
        '''
        return cloud.CloudConnection(project_id=project_id, session=self, **kwargs)
    
    def create_turbowarp_cloudconnection(self, project_id : int, *, username = None, **kwargs) -> cloud.TwCloudConnection:
        '''
        Create a cloud connection to a turbowarp project.
        '''
        username = username or self.username
        return cloud.TwCloudConnection(project_id=project_id, username=username, **kwargs)
    
    def create_tw_cloudconnection(self, *args, **kwargs):
        '''
        Same as create_turbowarp_cloudconnection
        '''
        return self.create_turbowarp_cloudconnection(*args, **kwargs)

    def create_cloud_socket(self, project_id : int, *, packet_size : int = 220, cloudconnection_kwargs : dict = None, security : tuple = None, **kwargs):
        '''
        Create a cloud socket to a project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_cloudconnection(project_id, warning_type=ErrorInCloudSocket, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)

    def create_turbowarp_cloud_socket(self, project_id : int, *, packet_size : int = 90000, cloudconnection_kwargs : dict = None, security : tuple = None, **kwargs):
        '''
        Create a cloud socket to a turbowarp project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_tw_cloudconnection(project_id, warning_type=ErrorInCloudSocket, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)
    
    def create_tw_cloud_socket(self, *args, **kwargs):
        '''
        Same as create_turbowarp_cloud_socket
        '''
        return self.create_turbowarp_cloud_socket(*args, **kwargs)