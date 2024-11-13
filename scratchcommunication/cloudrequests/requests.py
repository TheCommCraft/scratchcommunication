"""
Submodule for handling incoming requests.
"""
from __future__ import annotations
import re, warnings, ast, inspect, traceback, time
from inspect import Parameter
from copy import deepcopy
from typing import Union, Mapping, Sequence, Any, Callable, Self, Optional
from types import FunctionType
from func_timeout import StoppableThread
from scratchcommunication.cloud_socket import BaseCloudSocketConnection, AnyCloudSocket
from .basetypes import BaseRequestHandler, StopRequestHandler, SpecificRequestHandler

class RequestHandler(BaseRequestHandler):
    """
    Class for request handlers.
    """
    def __init__(self, *, cloud_socket : AnyCloudSocket, uses_thread : bool = False):
        super().__init__(cloud_socket=cloud_socket, uses_thread=uses_thread)
        self.requests = {}
        self.thread = None
        self.current_client = None
        self.current_client_username = None
        self.error_handler = None
        
    def request(self, func : Optional[FunctionType] = None, *, name : Optional[str] = None, auto_convert : bool = False, allow_python_syntax : bool = True, thread : bool = False) -> Optional[Callable]:
        """
        Decorator for adding requests.
        """
        if func:
            self.add_request(func, name=name, auto_convert=auto_convert, allow_python_syntax=allow_python_syntax, thread=thread)
            return None
        return lambda x : self.request(x, name=name, auto_convert=auto_convert, allow_python_syntax=allow_python_syntax)
    
    def add_request(self, func : FunctionType, *, name : Optional[str] = None, auto_convert : bool = False, allow_python_syntax : bool = True, thread : bool = False):
        """
        Method for adding requests.
        """
        request_handler = SpecificRequestHandler(func, name=name or func.__name__, auto_convert=auto_convert, allow_python_syntax=allow_python_syntax, thread=thread)
        self.requests[request_handler.name] = request_handler
    
    def start(self, *, thread : Optional[bool] = None, daemon_thread : bool = False, duration : Union[float, int, None] = None, cascade_stop : bool = True) -> Optional[Self]:
        """
        Method for starting the request handler.
        """
        if thread or (thread is None and self.uses_thread):
            self.uses_thread = True
            self.thread = StoppableThread(target=lambda : self.start(thread=False, duration=duration, cascade_stop=cascade_stop), daemon=daemon_thread)
            self.thread.start()
            return self
        self.cloud_socket.listen()
        clients : list[tuple[BaseCloudSocketConnection, str]] = []
        end_time = duration and (time.time() + duration)
        while (not end_time) or time.time() < end_time:
            _ = self.cloud_socket.any_update.wait(30)
            try:
                try:
                    clients.append(self.cloud_socket.accept(timeout=0))
                except TimeoutError:
                    pass
                for client, username in clients:
                    try:
                        msg = client.recv(timeout=0)
                    except TimeoutError:
                        continue
                    response = self.process_request(
                        msg=msg,
                        client=client,
                        username=username,
                        send_response=self.get_response_sender(client)
                    )
                    if response:
                        client.send(response)
            except Exception:
                try:
                    if self.current_client is not None:
                        self.current_client.emit("uncaught_error", uncaught_error=traceback.format_exc(), last_client=self.current_client, last_raw_request=msg)
                except Exception:
                    pass
                warnings.warn(f"There was an uncaught error in the request handler: \n{traceback.format_exc()}", RuntimeWarning)
        if cascade_stop:
            self.stop(cascade_stop=cascade_stop)
        return None
    
    def get_response_sender(self, client : BaseCloudSocketConnection) -> Callable[[str], None]:
        """
        Get a callable for sending responses.
        """
        return client.send

    def process_request(self, msg : str, client : BaseCloudSocketConnection, username : str, send_response : Callable[[str], None]) -> Optional[str]:
        """
        Process a request and respond to it.
        """
        response : Optional[str]
        try:
            self.current_client = client
            self.current_client_username = username
            raw_sub_requests = [raw_request.strip() for raw_request in msg.split(";")]
            sub_request_names = [re.match(r"\w+", raw_request) for raw_request in raw_sub_requests]
            sub_requests = []
            for req_name_match, raw_req in zip(sub_request_names, raw_sub_requests):
                if req_name_match is None:
                    continue
                req_name = req_name_match.group()
                using_python_syntax = re.match(r"\w+\(.*\)$", raw_req)
                python_syntax_allowed = self.requests[req_name].allow_python_syntax
                if using_python_syntax and python_syntax_allowed:
                    name, args, kwargs = parse_python_request(raw_req, req_name)
                    sub_requests.append((name, args, kwargs))
                if not using_python_syntax:
                    name, args, kwargs = parse_normal_request(raw_req, req_name)
                    sub_requests.append((name, args, kwargs))
                if using_python_syntax and not python_syntax_allowed:
                    raise PermissionError("Python syntax is not allowed for this.")
        except Exception:
            response = "The command syntax was wrong."
            try:
                if self.current_client is not None:
                    self.current_client.emit("invalid_syntax", content=msg, client=self.current_client)
            except Exception:
                pass
            warnings.warn("Received a request with an invalid syntax: \n"+traceback.format_exc(), RuntimeWarning)
        else:
            try:
                for idx, (name, args, kwargs) in enumerate(sub_requests):
                    self.dispatch_request(name, args=args, kwargs=kwargs, client=client, response=idx == len(sub_requests) - 1, send_response=send_response)
                response = None
            except Exception:
                response = "Something went wrong."
                warnings.warn(f"Something went wrong with a request: \n{traceback.format_exc()}", RuntimeWarning)
        return response
                
    def dispatch_request(self, name, *, args : Sequence[Any], kwargs : Mapping[str, Any], client : BaseCloudSocketConnection, response : bool = True, send_response : Callable[[str], None]) -> None:
        """
        Dispatch a request.
        """
        request_handling_function = self.requests[name]
        args, kwargs, return_converter = type_casting(func=request_handling_function.function, signature=inspect.signature(request_handling_function), args=args, kwargs=kwargs)
        def respond(retried = False):
            return self.execute_request(
                name=name,
                args=args,
                kwargs=kwargs,
                client=client,
                response=response,
                return_converter=return_converter,
                request_handling_function=request_handling_function,
                retried=retried,
                respond=respond,
                send_response=send_response
            )
        if request_handling_function.thread:
            thread = StoppableThread(target=respond)
            thread.start()
            return
        respond()
    
    def execute_request(
        self,
        name,
        *,
        args : Sequence[Any],
        kwargs : Mapping[str, Any],
        client : BaseCloudSocketConnection,
        response : bool = True,
        return_converter : Callable,
        request_handling_function : Callable,
        retried : bool = False,
        respond : Callable,
        send_response : Callable[[str], None]
    ) -> None:
        """
        Execute a request handler.
        """
        try:
            response_text = str(return_converter(request_handling_function(*args, **kwargs)))
        except ErrorMessage as e:
            response_text = " ".join(e.args)
        except Exception as e:
            if self.error_handler and not retried:
                try:
                    self.error_handler(e, lambda : respond(retried=True))
                    return
                except Exception:
                    try:
                        assert self.current_client is not None
                        self.current_client.emit("error_in_request", request=name, args=args, kwargs=kwargs, client=self.current_client, error=e)
                    except Exception:
                        pass
                    warnings.warn(f"Error in request couldn't be handled \"{name}\" with args: {args} and kwargs: {kwargs}: \n{traceback.format_exc()}", RuntimeWarning)
                    return
            try:
                assert self.current_client is not None
                self.current_client.emit("error_in_request", request=name, args=args, kwargs=kwargs, client=self.current_client, error=e)
            except Exception:
                pass
            warnings.warn(f"Error in request \"{name}\" with args: {args} and kwargs: {kwargs}: \n{traceback.format_exc()}", RuntimeWarning)
        if not response:
            return
        send_response(response_text)
    
    def stop(self, cascade_stop : bool = True):
        """
        Stop the request handler.
        """
        if self.uses_thread and self.thread is not None:
            self.thread.stop(StopRequestHandler)
        if cascade_stop:
            self.cloud_socket.stop(cascade_stop=cascade_stop)
            self.cloud_socket.any_update.set()
        if self.uses_thread and self.thread is not None:
            self.thread.join(5)
            
    def on_error(self, func : FunctionType):
        self.error_handler = func
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
                   
                   
KW = Parameter.KEYWORD_ONLY
KWPS = Parameter.POSITIONAL_OR_KEYWORD
PS = Parameter.POSITIONAL_ONLY
MKW = Parameter.VAR_KEYWORD
MPS = Parameter.VAR_POSITIONAL
DO_NOTHING = lambda x: x

def type_cast(func):
    def wrapper(*args, **kwargs):
        args, kwargs, return_ann = type_casting(func=func, signature=inspect.signature(func), args=args, kwargs=kwargs)
        return return_ann(func(*args, **kwargs))
    wrapper.__name__ = func.__name__
    return wrapper

def type_casting(*, func : FunctionType, signature : inspect.Signature, args : Sequence, kwargs : Mapping) -> tuple[tuple, dict, Callable]:
    args = list(deepcopy(args))
    kwargs = dict(deepcopy(kwargs))
    for idx, ((kw, param), arg) in enumerate(zip(signature.parameters.items(), args)):
        if param.kind in (PS, KWPS):
            if kw in kwargs:
                raise TypeError(f"{func.__name__}() got multiple values for argument '{kw}'")
            try:
                args[idx] = (param.annotation if not param.annotation in (Any, signature.empty) else DO_NOTHING)(arg)
            except TypeError:
                pass
        if param.kind == MPS:
            items_converter = (param.annotation if not param.annotation in (Any, signature.empty) else DO_NOTHING)
            item_converter = (items_converter.__args__[0] if hasattr(items_converter, "__args__") else DO_NOTHING) or DO_NOTHING
            try:
                args[idx:] = [item_converter(arg) for arg in items_converter(args[idx:])]
            except TypeError:
                pass
            
    last_idx = None
    for idx, (kw, arg) in enumerate(kwargs.items()):
        try:
            param = signature.parameters[kw]
            assert param.kind != MKW
        except (KeyError, AssertionError):
            last_idx = idx
            break
        if param.kind in (KW, KWPS):
            try:
                kwargs[kw] = (param.annotation if not param.annotation in (Any, signature.empty) else DO_NOTHING)(arg)
            except TypeError:
                pass
            
    if last_idx is not None:
        for param in signature.parameters.values():
            if param.kind == MKW:
                items_converter = (param.annotation if not param.annotation in (Any, signature.empty) else DO_NOTHING)
                item_converters = (items_converter.__args__[:2] if hasattr(items_converter, "__args__") else (DO_NOTHING, DO_NOTHING)) or (DO_NOTHING, DO_NOTHING)
                try:
                    kwargs.update({item_converters[0](k): item_converters[1](v) for k, v in dict(items_converter({i: j for i, j in list(kwargs.items())[last_idx:]})).items()})
                except TypeError:
                    pass
        
    return_callable = DO_NOTHING
    if signature.return_annotation != inspect.Signature.empty and signature.return_annotation != Any:
        return_callable = signature.return_annotation
    return (tuple(args), kwargs, return_callable)

def parse_python_request(msg : str, name : str) -> tuple[str, tuple[Any, ...], dict[Any, Any]]:
    """
    Parse a request in the format of a python function call.
    """
    parsed = getattr(ast.parse(msg).body[0], "value")
    assert getattr(parsed, "func").id == name
    name = getattr(parsed, "func").id
    args = [arg.value for arg in getattr(parsed, "args")]
    kwargs = {kwarg.arg: kwarg.value.value for kwarg in parsed.keywords}
    return (name, tuple(args), kwargs)

def parse_normal_request(msg : str, name : str) -> tuple[str, tuple[Any, ...], dict[Any, Any]]:
    """
    Parse a request in the normal format.
    """
    i = iter(msg)
    STR = "str"
    NUM = "num"
    FLT = "float"
    ID = "id"
    MT = "space"
    open_type = "'"
    mode = ID
    content = ""
    args : list[Any] = []
    while True:
        try:
            n = next(i)
            if mode == ID:
                if n == " ":
                    mode = MT
                    args.append(content)
                    content = ""
                    n = next(i)
                else:
                    content += n
            if mode == MT:
                if n in '\'"':
                    open_type = n
                    mode = STR
                    n = next(i)
                elif n.isnumeric() or n == ".":
                    mode = NUM
                else:
                    raise SyntaxError(n)
            if mode == FLT:
                if n == " ":
                    mode = MT
                    args.append(float(content))
                    content = ""
                    continue
                content += n
            if mode == NUM:
                if n == " ":
                    mode = MT
                    args.append(int(content))
                    content = ""
                    continue
                if n == ".":
                    mode = FLT
                content += n
            if mode == STR:
                if n == open_type:
                    n = next(i)
                    assert n == " "
                    mode = MT
                    args.append(content)
                    content = ""
                    continue
                if n == "\\":
                    n = next(i)
                content += n
        except StopIteration:
            args.append(float(content) if mode == FLT else (int(content) if mode == NUM else content))
            break
    assert args.pop(0) == name
    return (name, tuple(args), {})

class ErrorMessage(Exception):
    """
    Error with a message
    """


















