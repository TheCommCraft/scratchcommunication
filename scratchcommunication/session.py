import warnings
from .headers import headers
from .exceptions import InvalidValueError
import requests, json, re

class Session:
    def __init__(self, username : str = None, *, session_id : str):
        self.session_id = session_id
        self.username = username
        self.headers = headers
        self._login()
    def _login(self) -> None:
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
        except:
            raise Exception("An error occurred while trying to log in.")
    def create_cloudrequests_server(self, project_id : int, thread : bool = True):
        project_id = 1