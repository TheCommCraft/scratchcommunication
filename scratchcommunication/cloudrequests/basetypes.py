"""
Submodule for base types
"""
from __future__ import annotations
from func_timeout import StoppableThread
from typing import Union, Any, MutableMapping
from types import FunctionType
from dataclasses import dataclass, field
from scratchcommunication.cloud_socket import AnyCloudSocket, BaseCloudSocketConnection

@dataclass(slots=True)
class BaseRequestHandler:
    """
    Base class for request handlers.
    """
    project_id : int = field(init=False)
    cloud_socket : AnyCloudSocket = field(kw_only=True)
    requests : MutableMapping[str, SpecificRequestHandler] = field(init=False)
    uses_thread : bool = field(kw_only=True, default=False)
    thread : Union[StoppableThread, None] = field(init=False)
    current_client : Union[BaseCloudSocketConnection, None] = field(init=False)
    current_client_username : Union[str, None] = field(init=False)
    error_handler : Union[FunctionType, None] = field(init=False)

class StopRequestHandler(SystemExit):
    """
    Exception for stopping the request handler.
    """

class NotUsingAThread(Exception):
    """
    Exception for when something is not using a thread.
    """

@dataclass(slots=True, frozen=True)
class SpecificRequestHandler:
    function : FunctionType = field(repr=False, kw_only=False)
    name : str = field(kw_only=True)
    auto_convert : bool = field(kw_only=True)
    allow_python_syntax : bool = field(kw_only=True)
    thread : bool = field(kw_only=True)
    
    def __call__(self, *args, **kwargs) -> Any:
        return self.function(*args, **kwargs)
