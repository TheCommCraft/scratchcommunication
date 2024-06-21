from __future__ import annotations
from typing import Literal, Union, Any, Protocol, assert_never, TypeVar
from dataclasses import dataclass, field
from collections.abc import Callable
from functools import wraps
from .exceptions import QuickAccessDisabledError, NotSupported, ErrorInEventHandler, StopException, EventExpiredError
import scratchcommunication
from func_timeout import StoppableThread
import json, time, requests, warnings, traceback, secrets, sys, ssl
from websocket import WebSocket, WebSocketConnectionClosedException, WebSocketTimeoutException

@dataclass
class Context:
    _cloud : CloudConnection = field(kw_only=True)
    
    def set_var(self, name : str, value : Union[float, int, bool], *, name_literal : bool = False, context : Context = None):
        """
        Set a variable in this context.
        """
        return self._cloud.set_variable(name=name, value=value, name_literal=name_literal, context=context)
        
    def get_var(self, name : str, *, name_literal : bool = False, context : Context = None) -> Union[float, int, bool]:
        """
        Get a variable in this context.
        """
        return self._cloud.get_variable(name=name, name_literal=name_literal, context=context)
    
    def emit(self, event : Union[Event, Literal["set", "delete", "connect", "create"]], *, context : Context = None, **entries) -> int:
        """
        Emit an event in this context.
        """
        return self._cloud.emit_event(event, context=context, **entries)
    
    def get_cloud_connection(self):
        """
        Returns the assiociated cloud connection.
        """
        return self._cloud

class EventDispatcher(Protocol):
    def __call__(self, data : dict, **entries) -> None:
        pass

class Event(Context):
    _id : int = None
    value : Union[float, int, bool] = None
    var : str = None
    name : str = None
    project : CloudConnection = None
    type : str = None
    def __init__(self, _type: Literal["set", "delete", "connect", "create"], **entries):
        entries["type"] = _type
        self.__dict__.update(entries)
        self._data = None
        self.project = getattr(self, "project")
        self._id = secrets.randbits(16)

    @property
    def data(self):
        if not self.project.supports_cloud_logs:
            raise NotSupported("Cloud connection does not support cloud logs.")
        if self.type != "set":
            raise NotSupported("No setting")
        if not self._data:
            try:
                self._data = list(
                    filter(
                        lambda x: x["value"] == self.value,
                        self.project.get_cloud_logs(
                            project_id=self.project.project_id,
                            filter_by_name=self.var,
                            filter_by_name_literal=True,
                        ),
                    )
                )[self.project.get_age_of_event(self)]
            except IndexError:
                raise EventExpiredError("Event expired. (Cannot fetch data from Scratch server)")
        return self._data

    @property
    def user(self):
        return self.data["user"]

    @property
    def timestamp(self):
        return self.data["timestamp"]
    
    @property
    def _cloud(self):
        return self.project
    
    def __hash__(self):
        return hash(self._id)

class CloudConnection(Context):
    """
    Connect to a cloud server and set cloud variables.
    """
    project_id : int
    thread_running : bool
    warning_type : type[Warning]
    session : Any
    username : str
    quickaccess : bool
    reconnect : bool
    values : dict
    events : dict
    cloud_host : str
    accept_strs : bool
    wait_until : Union[float, int]
    receive_from_websocket : bool
    data_reception : Union[StoppableThread, None]
    event_order : dict[Union[float, int, bool], dict[Event, int]]
    processed_events : list[Event]
    keep_all_events : bool
    supports_cloud_logs : bool
    allow_no_certificate : bool
    def __init__(
        self,
        *,
        project_id : int,
        session : Any = None,
        username : str = None,
        quickaccess : bool = False,
        reconnect : bool = True,
        receive_from_websocket : bool = True,
        warning_type : type[Warning] = ErrorInEventHandler,
        daemon_thread : bool = False,
        connect : bool = True,
        keep_all_events : bool = False,
        allow_no_certificate : bool = False
    ):
        self.websocket = None
        self.allow_no_certificate = allow_no_certificate
        self.supports_cloud_logs = True
        self.keep_all_events = keep_all_events
        self.event_order = {}
        self.processed_events = []
        self.thread_running = True
        self.warning_type = warning_type
        self.project_id = project_id
        self.session = session
        self.username = username if username is not None else session.username
        self.quickaccess = quickaccess
        self.reconnect = reconnect
        self.values = {}
        self.events = {}
        self.cloud_host = "wss://clouddata.scratch.mit.edu"
        self.accept_strs = False
        self.wait_until = 0
        self.receive_from_websocket = receive_from_websocket
        self.data_reception = None
        if not connect:
            return
        self._handle_connect()
        if not self.receive_from_websocket:
            while True:
                try:
                    self.receive_new_data()
                    return
                except Exception:
                    self._handle_connect()
        self.data_reception = StoppableThread(target=self.receive_data, daemon=daemon_thread)
        self.data_reception.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_thread()

    def stop_thread(self):
        """
        Use for stopping the underlying thread.
        """
        self.thread_running = False
        self.data_reception.stop(StopException, 0.1)
        self.data_reception.join(5)
        
    def enable_quickaccess(self):
        """
        Use for enabling the use of the object as a lookup table.
        """
        self.quickaccess = True

    def disable_quickaccess(self):
        """
        Use for disabling the use of the object as a lookup table.
        """
        self.quickaccess = False

    def _connect(self, no_cert : bool = False):
        self.websocket = WebSocket(sslopt=({"cert_reqs": ssl.CERT_NONE} if no_cert else None))
        self.websocket.connect(
            "wss://clouddata.scratch.mit.edu",
            cookie="scratchsessionsid=" + self.session.session_id + ";",
            origin="https://scratch.mit.edu",
            enable_multithread=True,
            timeout=5
        )
    
    def _handle_connect(self, *, retry : int = 3) -> Union[Exception, None]:
        """
        Don't use this.
        """
        try:
            self._connect()
            self.handshake()
            self.emit_event("connect", timestamp=time.time())
        except ssl.SSLCertVerificationError:
            if not self.allow_no_certificate:
                return ConnectionError(
                    "The SSL certificate could not be verified. Add allow_no_certificate=True to allow a connection without a certificate."
                )
            warnings.warn("Connecting without a certificate.", RuntimeWarning)
            self._connect(no_cert=True)
        except Exception as e:
            if retry == 1:
                return ConnectionError(
                    "There was an error while connecting to the cloud server."
                )
            exc = self._handle_connect(retry=retry - 1)
            if exc:
                raise exc from e

    def handshake(self):
        self.send_packet(
            {
                "method": "handshake",
                "user": self.username,
                "project_id": self.project_id,
            }
        )

    def send_packet(self, packet):
        """
        Don't use this.
        """
        self.websocket.send(json.dumps(packet) + "\n")

    @staticmethod
    def get_cloud_logs(
        *,
        project_id : str,
        limit : int = 100,
        filter_by_name : Union[str, None] = None,
        filter_by_name_literal : bool = False,
    ) -> list:
        """
        Use for getting the cloud logs of a project.
        """
        logs = []
        filter_by_name = (
            filter_by_name
            if filter_by_name_literal
            else "☁ " + filter_by_name.removeprefix("☁ ")
            if filter_by_name
            else None
        )
        offset = 0
        while len(logs) < limit:
            data = requests.get(
                f"https://clouddata.scratch.mit.edu/logs?projectid={project_id}&limit={limit}&offset={offset}",
                timeout=10
            ).json()
            logs.extend(
                data
                if filter_by_name is None
                else filter(lambda x: x["name"] == filter_by_name, data)
            )
            offset += len(data)
            if len(data) == 0:
                break
        return logs[:limit]

    def verify_value(self, value : Union[float, int, bool]):
        """
        Use for detecting if a value can be used for cloud variables.
        """
        try:
            float(value)
            assert len(json.dumps(value)) <= 256
        except Exception as e:
            raise ValueError("Bad value for cloud variables.") from e

    def _set_variable(
        self, *, name : str, value : Union[float, int, bool], retry : int
    ):
        """
        Don't use this.
        """
        try:
            self.send_packet(
                {
                    "method": "set",
                    "name": name,
                    "value": value,
                    "user": self.username,
                    "project_id": self.project_id,
                }
            )
        except ConnectionError as e:
            raise e
        except Exception as e:
            if not self.reconnect:
                raise ConnectionError(
                    "There was an error while setting the cloud variable."
                ) from e
            if retry == 1:
                raise ConnectionError(
                    "There was an error while setting the cloud variable."
                ) from e
            self._handle_connect()
            self._set_variable(name=name, value=value, retry=retry - 1)

    def set_variable(
        self,
        *,
        name : str,
        value : Union[float, int, bool],
        name_literal : bool = False,
        context : Context = None
    ):
        """
        Use for setting a cloud variable.
        """
        context = context or self
        assert context is self or context._cloud is self, "Wrong context"
        self.verify_value(value)
        name = name if name_literal else "☁ " + name.removeprefix("☁ ")
        time.sleep(max(0, self.wait_until - time.time()))
        self.wait_until = time.time() + 0.1

        self._set_variable(name=name, value=value, retry=10)
        self.values[name] = value
        self.emit_event(
            "set",
            name=name.removeprefix("☁ "),
            var=name,
            value=value,
            timestamp=time.time(),
        )

    def get_variable(
        self, *, name : str, name_literal : bool = False, context : Context = None
    ) -> Union[float, int, bool]:
        """
        Use for getting the value of a cloud variable.
        """
        context = context or self
        assert context is self or context._cloud is self, "Wrong context"
        name = name if name_literal else "☁ " + name.removeprefix("☁ ")
        if self.receive_from_websocket:
            try:
                return (self.values[name])
            except Exception:
                pass
        try:
            return (self.get_cloud_logs(
                project_id=self.project_id,
                limit=1,
                filter_by_name=name,
                filter_by_name_literal=True,
            )[0]["value"])
        except (IndexError, NotSupported):
            return (self.values[name])

    def __getitem__(self, item : str) -> Union[float, int, bool]:
        if not self.quickaccess:
            raise QuickAccessDisabledError("Quickaccess is disabled")
        return self.get_variable(name=item)

    def __setitem__(self, item : str, value : Union[float, int, bool]):
        if not self.quickaccess:
            raise QuickAccessDisabledError("Quickaccess is disabled")
        self.set_variable(name=item, value=value)

    def receive_new_data(self, first : bool = False) -> dict:
        """
        Use for receiving new cloud data.
        """
        data = [json.loads(j) for j in self.websocket.recv().split("\n") if j]
        
        for i in data:
            i["var"] = i["name"]
            i["name"] = i["name"].removeprefix("☁ ")
            method = i.pop("method")
            if not first:
                self.emit_event(method, **i)
            if method == "set":
                self.values[i["var"]] = i["value"]
        return self.values

    def _prepare_handle_connection(self):
        while self.thread_running:
            try:
                self.receive_new_data(first=True)
                break
            except WebSocketTimeoutException:
                pass
            except WebSocketConnectionClosedException:
                self._handle_connect()

    def receive_data(self):
        """
        Use for receiving cloud data.
        """
        self._prepare_handle_connection()
        while self.thread_running:
            try:
                self.receive_new_data()
            except WebSocketTimeoutException:
                pass
            except WebSocketConnectionClosedException:
                self._handle_connect()
                self._prepare_handle_connection()
                    
    def get_age_of_event(self, event : Event) -> int:
        """
        Do not use.
        """
        try:
            return len(self.event_order.get(event.value, {})) - self.event_order.get(event.value, {})[event] - 1
        except KeyError:
            raise ValueError("No such event")

    def emit_event(self, event : Union[Literal["set", "delete", "connect", "create"], Event], context : Context = None, **entries) -> int:
        """
        Use for emitting events. Returns how many handlers could handle the event.
        """
        context = context or self
        assert context is self or context._cloud is self, "Wrong context"
        data = event if isinstance(event, Event) else Event(event, **entries)
        data.project = self
        if isinstance(event, Event):
            event = event.type
        if not self.event_order.get(data.value):
            self.event_order[data.value] = {}
        self.event_order[data.value][data] = len(self.event_order[data.value])
        amount = self._emit_event(event, data) + self._emit_event("any", data)
        self.processed_events.append(data)
        if not self.keep_all_events:
            self.garbage_disposal_of_events()
        return amount
    
    def garbage_disposal_of_events(self, force_disposal : bool = False) -> int:
        """
        Dispose of all unused events
        """
        if self.keep_all_events and not force_disposal:
            warnings.warn("Attempted to dispose of all events with keep_all_events enabled. Try to set force_disposal=True in order to force garbage disposal.", UserWarning)
            return
        for event in self.processed_events.copy():
            if sys.getrefcount(event) <= 5:
                self.processed_events.remove(event)
                self.event_order.get(event.value).pop(event)

    def _emit_event(self, event : Literal["set", "delete", "connect", "create", "any"], data : Event) -> int:
        """
        Don't use this.
        """
        amount = 0
        if not event in self.events:
            return 0
        for i in self.events[event]:
            try:
                i(data)
                amount += 1
            except Exception:
                warnings.warn(
                    f"There was an exception while trying to process an event: {traceback.format_exc()}",
                    self.warning_type
                )
        return amount

    def on(self, event : Literal["set", "delete", "connect", "create", "any"]) -> Callable[[Callable[[Event], None]], EventDispatcher]:
        """
        Register a new event.
        """

        def wrapper(func):
            if event in self.events:
                eventlist = self.events[event]
            else:
                eventlist = self.events[event] = []
            eventlist.append(func)
            @wraps(func)
            def dispatcher(data : dict = None, /, *, context : Context = None, **entries):
                return self.emit_event(event, context=context, **data, **entries)
            return dispatcher

        return wrapper
    
    @property
    def _cloud(self):
        return self


class TwCloudConnection(CloudConnection):
    """
    Connect to a non scratch cloud server and set cloud variables.
    """
    contact_info : str
    user_agent : str
    def __init__(
        self, 
        *, 
        project_id : str, 
        username : str = "player1000", 
        session : Any = None, 
        quickaccess : bool = False, 
        reconnect : bool = True, 
        receive_from_websocket : bool = True, 
        warning_type : type[Warning] = ErrorInEventHandler,
        daemon_thread : bool = False, 
        cloud_host : str = "wss://clouddata.turbowarp.org/", 
        accept_strs : bool = False,
        keep_all_events : bool = False,
        contact_info : str,
        allow_no_certificate : bool = False
    ):
        super().__init__(
            project_id=project_id, 
            username=username,
            session=session,
            quickaccess=quickaccess,
            reconnect=reconnect,
            receive_from_websocket=receive_from_websocket,
            warning_type=warning_type,
            daemon_thread=daemon_thread,
            connect=False,
            keep_all_events=keep_all_events,
            allow_no_certificate=allow_no_certificate
        )
        self.supports_cloud_logs = False
        self.contact_info = contact_info or ((f"@{session.username} on scratch" if session else "Anonymous") if username == "player1000" else f"@{username} on scratch")
        assert self.contact_info != "Anonymous", "You need to specify your contact_info for the turbowarp cloud."
        self.user_agent = f"scratchcommunication/{scratchcommunication.__version_number__} - {self.contact_info}"
        self.cloud_host = cloud_host
        self.accept_strs = accept_strs
        self._handle_connect()
        if not self.receive_from_websocket:
            while True:
                try:
                    self.receive_new_data()
                    return
                except Exception:
                    self._handle_connect()
        self.data_reception = StoppableThread(target=self.receive_data, daemon=daemon_thread)
        self.data_reception.start()
        
    def _connect(self, no_cert : bool = False):
        self.websocket = WebSocket(sslopt=({"cert_reqs": ssl.CERT_NONE} if no_cert else None))
        self.websocket.connect(self.cloud_host, enable_multithread=True, timeout=5, header={"User-Agent": self.user_agent})

    @staticmethod
    def get_cloud_logs(*args, **kwargs):
        raise NotSupported("This can't be used on turbowarp.")

    def verify_value(self, value: Union[float, int, bool, str]):
        """
        Use for detecting if a value can be used for cloud variables.
        """
        try:
            float(value)
        except Exception as e:
            if self.accept_strs and isinstance(value, str):
                return
            raise ValueError("Bad value for cloud variables.") from e


class Sky(CloudConnection):
    """
    Multiple cloud connections in one.
    """
    def __init__(self, *clouds):
        self.clouds = clouds
        
    def stop_thread(self):
        """
        Use for stopping the underlying threads.
        """
        for cloud in self.clouds:
            cloud.stop_thread()
        
    def set_variable(
        self,
        *,
        name : str,
        value : Union[float, int, bool],
        name_literal : bool = False,
        context : Context
    ):
        """
        Use for setting a cloud variable.
        """
        assert context in self.clouds or context._cloud in self.clouds, "Wrong context"
        assert not (context is self or context._cloud is self), "Bad context"
        context.set_var(name=name, value=value, name_literal=name_literal, context=context)
        
    def get_variable(
        self,
        *,
        name : str,
        name_literal : bool = False,
        context : Context
    ) -> Union[float, int, bool]:
        """
        Use for setting a cloud variable.
        """
        assert context in self.clouds or context._cloud in self.clouds, "Wrong context"
        assert not (context is self or context._cloud is self), "Bad context"
        return context.get_var(name=name, name_literal=name_literal, context=context)

    def emit_event(self, event : Union[Literal["set", "delete", "connect", "create"], Event], context : Context, **entries) -> int:
        """
        Use for emitting events. Returns how many handlers could handle the event.
        """
        assert context in self.clouds or context._cloud in self.clouds, "Wrong context"
        assert not (context is self or context._cloud is self), "Bad context"
        return context.emit(event, context=context, **entries)
        
    def on(self, event : Literal["set", "delete", "connect", "create", "any"]) -> Callable[[Callable[[Event], None]], EventDispatcher]:
        """
        Register a new event.
        """
        def wrapper(func):
            for cloud in self.clouds:
                cloud.on(event)(func)
            @wraps(func)
            def dispatcher(data : dict = None, /, *, context : Context, **entries):
                return self.emit_event(event, context=context, **data, **entries)
            return dispatcher

        return wrapper
    
    @property
    def _cloud(self):
        raise NotImplementedError