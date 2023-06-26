import warnings
from .headers import headers
from .exceptions import InvalidValueError
from . import cloud, cloud_socket
import requests, json, re

class Session:
    def __init__(self, username : str = None, *, session_id : str):
        self.session_id = session_id
        self.username = username
        self.headers = headers
        self._login()

    def _login(self):
        '''
        Don't use this
        '''
        self.cookies = {
            "scratchcsrftoken" : "a",
            "scratchlanguage" : "en",
            "scratchpolicyseen": "true",
            "scratchsessionsid" : self.session_id,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        account = requests.post("https://scratch.mit.edu/session", headers=self.headers, cookies={
            "scratchsessionsid": self.session_id,
            "scratchcsrftoken": "a",
            "scratchlanguage": "en",
        }).json()
        self.xtoken = account["user"]["token"]
        self.headers["X-Token"] = self.xtoken

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
                    }
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

    def create_cloud_socket(self, project_id : int, *, packet_size : int = 220):
        '''
        Create a cloud socket to a project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_cloudconnection(project_id), packet_size=packet_size)