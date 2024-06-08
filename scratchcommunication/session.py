import warnings
import requests, json, re
from typing import Literal, Self, assert_never, Union
from .headers import headers
from .exceptions import InvalidValueError, ErrorInCloudSocket, NotSupported
from . import cloud, cloud_socket
from . import security as sec
try:
    import browsercookie
    browsercookie_err = None
except Exception as e:
    browsercookie = None
    browsercookie_err = e

FIREFOX = 0
CHROME = 1
EDGE = 2
SAFARI = 3
CHROMIUM = 4
EDGE_DEV = 5
VIVALDI = 6
ANY = 7

class Session:
    __slots__ = ("session_id", "username", "headers", "cookies", "xtoken", "email", "id", "permissions", "flags", "banned", "session_data", "mute_status", "new_scratcher")
    def __init__(self, username : str = None, *, session_id : str = None, xtoken : str = None, _login : bool = True):
        if not _login:
            return
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
        self._login(xtoken=xtoken)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def logout(self):
        for attr in self.__slots__:
            delattr(self, attr)

    def _login(self, *, xtoken : str = None, _session : requests.Session = None):
        '''
        Don't use this
        '''
        try:
            account = (_session or requests).post("https://scratch.mit.edu/session", headers=self.headers, cookies={
                "scratchsessionsid": self.session_id,
                "scratchcsrftoken": "a",
                "scratchlanguage": "en",
            }).json()
            self.supply_xtoken(account["user"]["token"])
            self.username = account["user"]["username"]
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
                raise ValueError("No username supplied and there was none found. The username is needed.")
            warnings.warn("Couldn't find XToken. Most features will probably still work.")
            if xtoken:
                self.supply_xtoken(xtoken)
                warnings.warn("Got XToken from login data.")
                
    def supply_xtoken(self, xtoken):
        self.xtoken = xtoken
        self.headers["X-Token"] = xtoken

    @classmethod
    def from_browser(cls, browser : Literal[0,1,2,3,4,5,6,7]) -> Self:
        """
        Import cookies from browser to login
        """
        if not browsercookie:
            raise NotSupported("You cannot use browsercookie") from browsercookie_err
        match browser:
            case 0:
                cookies = browsercookie.firefox()
            case 1:
                cookies = browsercookie.chrome()
            case 2:
                cookies = browsercookie.edge()
            case 3:
                cookies = browsercookie.safari()
            case 4:
                cookies = browsercookie.chromium()
            case 5:
                cookies = browsercookie.edge_dev()
            case 6:
                cookies = browsercookie.vivaldi()
            case 7:
                cookies = browsercookie.load()
            case _:
                assert_never(browser)
        
        with requests.Session() as session:
            session.cookies.update(cookies)
            session.headers.update(headers)
            obj = cls(_login=False)
            obj.cookies = {
                "scratchcsrftoken" : "a",
                "scratchlanguage" : "en",
                "scratchpolicyseen": "true",
                "accept": "application/json",
                "Content-Type": "application/json",
            }
            obj.cookies.update(session.cookies.get_dict(".scratch.mit.edu"))
            obj.session_id = session.cookies.get_dict(".scratch.mit.edu").get("scratchsessionsid")
            obj.headers = session.headers
            obj._login(_session=session)
            return obj

    @classmethod
    def login(cls, username : str, password : str) -> Self:
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
    
    def create_turbowarp_cloudconnection(self, project_id : str, *, username = None, **kwargs) -> cloud.TwCloudConnection:
        '''
        Create a cloud connection to a turbowarp project.
        '''
        username = username or self.username
        return cloud.TwCloudConnection(project_id=project_id, username=username, session=self, **kwargs)
    
    def create_tw_cloudconnection(self, *args, **kwargs):
        '''
        Same as create_turbowarp_cloudconnection
        '''
        return self.create_turbowarp_cloudconnection(*args, **kwargs)

    def create_cloud_socket(self, project_id : int, *, packet_size : int = 220, cloudconnection_kwargs : dict = None, security : Union[None, tuple, sec.Security] = None, **kwargs):
        '''
        Create a cloud socket to a project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_cloudconnection(project_id, warning_type=ErrorInCloudSocket, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)

    def create_turbowarp_cloud_socket(self, contact_info : str, project_id : str, *, packet_size : int = 90000, cloudconnection_kwargs : dict = None, security : Union[None, tuple, sec.Security] = None, **kwargs):
        '''
        Create a cloud socket to a turbowarp project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_tw_cloudconnection(project_id, contact_info=contact_info, warning_type=ErrorInCloudSocket, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)
    
    def create_tw_cloud_socket(self, *args, **kwargs):
        '''
        Same as create_turbowarp_cloud_socket
        '''
        return self.create_turbowarp_cloud_socket(*args, **kwargs)