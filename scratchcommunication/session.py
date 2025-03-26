import warnings
import json, re
from base64 import b64decode, b64encode
from typing import Literal, Self, Union, overload, Optional
from types import NoneType
from abc import ABC, abstractmethod
from http.cookiejar import CookieJar
import requests
from super_session_keys import SessionKeysServer
from .commons import get_headers, get_cookies, Browser
from .exceptions import ErrorInCloudSocket, NotSupported, LoginFailure
from . import cloud, cloud_socket
from . import security as sec
try:
    import browsercookie
    browsercookie_err = None
except Exception as e:
    browsercookie = None
    browsercookie_err = e
    
FIREFOX = Browser.FIREFOX
CHROME = Browser.CHROME
EDGE = Browser.EDGE
SAFARI = Browser.SAFARI
CHROMIUM = Browser.CHROMIUM
EDGE_DEV = Browser.EDGE_DEV
VIVALDI = Browser.VIVALDI
ANY = Browser.ANY

class Sessionable(ABC):
    @property
    @abstractmethod
    def session_string(self) -> bytes:
        pass
    
    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return ("session_string" in subclass.__dict__) or NotImplemented

    
class Session(Sessionable):
    __slots__ = ("session_id", "username", "password", "headers", "cookies", "xtoken", "email", "id", "permissions", "flags", "banned", "session_data", "mute_status", "new_scratcher")
    @overload
    def __init__(self, username : Optional[str] = None, *, session_id : Optional[str] = None, xtoken : Optional[str] = None, _login : bool = True):
        """
        Create a session from a cookie.
        """
        
    @overload
    def __init__(self, sessionable : Union[Sessionable, bytes]):
        """
        Create a session from another.
        """
        
    @overload
    def __init__(self, username : str, password : str):
        """
        Create a session from login data
        """
    
    def __init__(self, username_or_sessionable = None, password = None, *, session_id = None, xtoken = None, _login = True):
        if (isinstance(username_or_sessionable, Sessionable) or hasattr(username_or_sessionable, "session_string")) or isinstance(username_or_sessionable, bytes):
            if (isinstance(username_or_sessionable, Sessionable) or hasattr(username_or_sessionable, "session_string")):
                session_string = username_or_sessionable.session_string
            else:
                session_string = username_or_sessionable
            self._login_from_session_string(session_string)
            return
        elif isinstance(username_or_sessionable, str) and isinstance(password, str):
            self.password = password
        elif isinstance(username_or_sessionable, str) and isinstance(password, NoneType):
            pass
        if not _login:
            return
        self.session_id = session_id
        self.username = username_or_sessionable
        self.headers = get_headers()
        self.cookies = get_cookies()
        self._login(xtoken=xtoken)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def logout(self):
        for attr in self.__slots__:
            delattr(self, attr)
            
    def _login_from_session_string(self, session_string : bytes) -> None:
        session_data = load_session_string(session_string)
        self.password = session_data.get("password")
        xtoken = session_data.get("xtoken")
        self.session_id = session_data.get("session_id")
        self.username = session_data.get("username")
        self.headers = get_headers()
        self.cookies = get_cookies()
        try:
            self._login(xtoken=xtoken, dont_catch=True)
            return
        except Exception:
            pass
        key_server = SessionKeysServer(mapping_id=session_string + b"@scratchcommunication_login")
        try:
            self.session_id = key_server["session_id"]
            xtoken = key_server["xtoken"]
            self._login(xtoken=xtoken, dont_catch=True)
            return
        except Exception:
            pass
        try:
            self.session_id = self._session_id_by_login()
            self._login(dont_catch=True)
            key_server["session_id"] = self.session_id
            key_server["xtoken"] = self.xtoken
            return
        except Exception:
            raise LoginFailure("Couldn't login with session string.") from None

    def _login(self, *, xtoken : Optional[str] = None, _session : Optional[requests.Session] = None, dont_catch : bool = False) -> None:
        '''
        Don't use this
        '''
        try:
            assert self.session_id
            self.cookies["scratchsessionsid"] = self.session_id
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
        except Exception as e:
            if dont_catch:
                raise e from None
            if self.username is None:
                raise LoginFailure("No username supplied and there was none found. The username is needed.") from None
            if hasattr(self, "password"):
                self.session_id = self._session_id_by_login()
                return self._login()
            warnings.warn("Couldn't find XToken. Most features will probably still work.")
            if xtoken:
                self.supply_xtoken(xtoken)
                warnings.warn("Got XToken from login data.")
             
    def _session_id_by_login(self) -> str:
        try:
            result = re.search('"(.*)"', requests.post(
                "https://scratch.mit.edu/login/",
                data=json.dumps({
                    "username": self.username,
                    "password": self.password
                }),
                headers=get_headers(),
                cookies={
                    "scratchcsrftoken": "a",
                    "scratchlanguage": "en"
                },
                timeout=10
            ).headers["Set-Cookie"])
            assert result is not None
            return str(result.group())
        except Exception as e:
            raise LoginFailure("An error occurred while trying to log in.") from e
                
    def supply_xtoken(self, xtoken):
        self.xtoken = xtoken
        self.headers["X-Token"] = xtoken

    @classmethod
    def from_browser(cls, browser : Browser) -> Self:
        """
        Import cookies from browser to login
        """
        if not browsercookie:
            raise NotSupported("You cannot use browsercookie") from browsercookie_err
        cookies : Optional[CookieJar] = None
        if browser == ANY:
            cookies = browsercookie.load()
        elif browser == FIREFOX:
            cookies = browsercookie.firefox()
        elif browser == CHROME:
            cookies = browsercookie.chrome()
        elif browser == EDGE:
            cookies = browsercookie.edge()
        elif browser == SAFARI:
            cookies = browsercookie.safari()
        elif browser == CHROMIUM:
            cookies = browsercookie.chromium()
        elif browser == EDGE_DEV:
            cookies = browsercookie.edge_dev()
        elif browser == VIVALDI:
            cookies = browsercookie.vivaldi()
        assert cookies is not None
        
        with requests.Session() as session:
            session.cookies.update(cookies)
            session.headers.update(get_headers())
            obj = cls(_login=False)
            obj.cookies = get_cookies()
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
        return cls(username, password)
        
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

    def create_cloud_socket(self, project_id : int, *, packet_size : Union[int, Literal["AUTO"]] = "AUTO", cloudconnection_kwargs : Optional[dict] = None, security : Union[None, tuple, sec.Security] = None, allow_no_certificate : bool = False, **kwargs):
        '''
        Create a cloud socket to a project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_cloudconnection(project_id, warning_type=ErrorInCloudSocket, allow_no_certificate=allow_no_certificate, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)

    def create_turbowarp_cloud_socket(self, project_id : str, contact_info : str, *, packet_size : Union[int, Literal["AUTO"]] = "AUTO", cloudconnection_kwargs : Optional[dict] = None, security : Union[None, tuple, sec.Security] = None, allow_no_certificate : bool = False, **kwargs):
        '''
        Create a cloud socket to a turbowarp project.
        '''
        return cloud_socket.CloudSocket(cloud=self.create_tw_cloudconnection(project_id, contact_info=contact_info, warning_type=ErrorInCloudSocket, allow_no_certificate=allow_no_certificate, **(cloudconnection_kwargs if cloudconnection_kwargs else {})), packet_size=packet_size, security=security, **kwargs)
    
    def create_tw_cloud_socket(self, *args, **kwargs):
        '''
        Same as create_turbowarp_cloud_socket
        '''
        return self.create_turbowarp_cloud_socket(*args, **kwargs)
    
    @property
    def session_string(self) -> bytes:
        session_data = {}
        session_data["username"] = self.username
        session_data["session_id"] = self.session_id
        try:
            session_data["xtoken"] = self.xtoken
        except AttributeError:
            pass
        try:
            session_data["password"] = self.password
        except AttributeError:
            pass
        return dump_session_data(session_data)

def load_session_string(session_string : bytes) -> dict[str, str]:
    decoded_session_string = b64decode(session_string).decode()
    session_data = json.loads(decoded_session_string)
    return session_data

def dump_session_data(session_data : dict[str, str]) -> bytes:
    return b64encode(json.dumps(session_data).encode("utf-8"))

def afbiaskasdhfuahbf(wa):
    """
    (I don't remember adding this.)
    """
    import aiortc
    aiortc.RTCPeerConnection()
