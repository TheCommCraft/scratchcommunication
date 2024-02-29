from typing import Literal, Union, Any
from .exceptions import QuickAccessDisabledError, NotSupported, ErrorInEventHandler, StopException
import json, time, requests, warnings, traceback
from websocket import WebSocket
from func_timeout import StoppableThread

NoneType = type(None)
CloudConnection = None

class Event:
    value : Union[float, int, bool] = None
    var : str = None
    name : str = None
    project : CloudConnection = None
    def __init__(self, _type: Literal["set", "delete", "connect", "create"], **entries):
        entries["type"] = _type
        self.__dict__.update(entries)
        self._data = None
        self.project = getattr(self, "project")

    @property
    def data(self):
        if not hasattr(self, "var"):
            raise NotSupported("No setting")
        if not self._data:
            self._data = list(
                filter(
                    lambda x: x["value"] == self.value,
                    self.project.get_cloud_logs(
                        project_id=self.project.project_id,
                        filter_by_name=self.var,
                        filter_by_name_literal=True,
                    ),
                )
            )[0]
        return self._data

    @property
    def user(self):
        return self.data["user"]

    @property
    def timestamp(self):
        return self.data["timestamp"]


class CloudConnection:
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
    data_reception : Any
    def __init__(
        self,
        *,
        project_id : int,
        session = None,
        username : str = None,
        quickaccess : bool = False,
        reconnect : bool = True,
        receive_from_websocket : bool = True,
        warning_type : type[Warning] = ErrorInEventHandler,
        daemon_thread : bool = False,
        connect : bool = True
    ):
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
        self._connect()
        if not self.receive_from_websocket:
            while True:
                try:
                    self.receive_new_data()
                    return
                except Exception:
                    self._connect()
        self.data_reception = StoppableThread(target=self.receive_data, daemon=daemon_thread)
        self.data_reception.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def stop_thread(self):
        """
        Use for stopping the underlying thread.
        """
        self.thread_running = False
        self.data_reception.stop(StopException)

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

    def _connect(self, *, retry : int = 10):
        """
        Don't use this.
        """
        try:
            self.websocket = WebSocket()
            self.websocket.connect(
                "wss://clouddata.scratch.mit.edu",
                cookie="scratchsessionsid=" + self.session.session_id + ";",
                origin="https://scratch.mit.edu",
                enable_multithread=True,
            )
            self.handshake()
            self.emit_event("connect", timestamp=time.time())
        except Exception as e:
            if retry == 1:
                raise ConnectionError(
                    f"There was an error while connecting to the cloud server."
                ) from e
            self._connect(retry=retry - 1)

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
            self._connect()
            self._set_variable(name=name, value=value, retry=retry - 1)

    def set_variable(
        self,
        *,
        name : str,
        value : Union[float, int, bool],
        name_literal : bool = False,
    ):
        """
        Use for setting a cloud variable.
        """
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
        self, *, name : str, name_literal : bool = False
    ) -> Union[float, int, bool]:
        """
        Use for getting the value of a cloud variable.
        """
        name = name if name_literal else "☁ " + name.removeprefix("☁ ")
        if self.receive_from_websocket:
            try:
                return self.values[name]
            except Exception:
                pass
        try:
            return self.get_cloud_logs(
                project_id=self.project_id,
                limit=1,
                filter_by_name=name,
                filter_by_name_literal=True,
            )[0]["value"]
        except (IndexError, NotSupported):
            return self.values[name]

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
            i["name"] = i["name"].replace("☁ ", "", 1)
            method = i.pop("method")
            if not first:
                self.emit_event(method, **i)
            if method == "set":
                self.values[i["var"]] = i["value"]
        return self.values

    def receive_data(self):
        """
        Use for receiving cloud data.
        """
        while self.thread_running:
            try:
                self._connect()
                self.receive_new_data(first=True)
                break
            except Exception:
                pass
        while self.thread_running:
            try:
                self.receive_new_data()
            except Exception:
                while self.thread_running:
                    try:
                        self._connect()
                        self.receive_new_data(first=True)
                        break
                    except Exception:
                        pass

    def emit_event(self, event : Union[Literal["set", "delete", "connect", "create"], Event], **entries) -> int:
        """
        Use for emitting events. Returns how many handlers could handle the event.
        """
        data = event if isinstance(event, Event) else Event(event, **entries)
        data.project = self
        if isinstance(event, Event):
            event = event.type
        return self._emit_event(event, data) + self._emit_event("any", data)

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

    def on(self, event : Literal["set", "delete", "connect", "create", "any"]):
        """
        Register a new event.
        """

        def wrapper(func):
            if event in self.events:
                eventlist = self.events[event]
            else:
                eventlist = self.events[event] = []
            eventlist.append(func)

        return wrapper


class TwCloudConnection(CloudConnection):
    def __init__(
        self, 
        *, 
        project_id : int, 
        username : str = "player1000", 
        quickaccess : bool = False, 
        reconnect : bool = True, 
        receive_from_websocket : bool = True, 
        warning_type : type[Warning] = ErrorInEventHandler,
        daemon_thread : bool = False, 
        cloud_host : str = "wss://clouddata.turbowarp.org/", 
        accept_strs : bool = False
    ):
        super().__init__(
            self,
            project_id=project_id, 
            username=username,
            quickaccess=quickaccess,
            reconnect=reconnect,
            receive_from_websocket=receive_from_websocket,
            warning_type=warning_type,
            daemon_thread=daemon_thread,
            connect=False
        )
        self.cloud_host = cloud_host
        self.accept_strs = accept_strs
        self._connect()
        if not self.receive_from_websocket:
            while True:
                try:
                    self.receive_new_data()
                    return
                except Exception:
                    self._connect()
        self.data_reception = StoppableThread(target=self.receive_data, daemon=daemon_thread)
        self.data_reception.start()

    def _connect(self, *, cloud_host = None, retry : int = 10):
        try:
            if cloud_host is not None:
                self.cloud_host = cloud_host
            self.websocket = WebSocket()
            self.websocket.connect(self.cloud_host, enable_multithread=True, timeout=10)
            self.handshake()
            self.emit_event("connect")
        except Exception as e:
            if retry == 1:
                raise ConnectionError(
                    f"There was an error while connecting to the cloud server."
                ) from e
            self._connect(cloud_host=cloud_host, retry=retry - 1)

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