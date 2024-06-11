"""
Submodule for handling incoming requests.
"""
import re, warnings, ast, inspect, traceback, time
from inspect import Parameter
from copy import deepcopy
from typing import Union, Mapping, Sequence, Any, Callable
from types import FunctionType
from func_timeout import StoppableThread
from scratchcommunication.cloud_socket import CloudSocketConnection, CloudSocket
from .basetypes import BaseRequestHandler, StopRequestHandler, NotUsingAThread

class RequestHandler(BaseRequestHandler):
    """
    Class for request handlers.
    """
    def __init__(self, *, cloud_socket : CloudSocket, uses_thread : bool = False):
        super().__init__(cloud_socket=cloud_socket, uses_thread=uses_thread)
        self.project_id = self.cloud_socket.cloud.project_id
        self.requests = {}
        self.thread = None
        self.current_client = None
        self.current_client_username = None
        
    def request(self, func : FunctionType = None, *, name : str = None, auto_convert : bool = False, allow_python_syntax : bool = True, thread : bool = False) -> Union[FunctionType, None]:
        """
        Decorator for adding requests.
        """
        if func:
            func.__req_name__ = name or func.__name__
            func.auto_convert = auto_convert
            func.allow_python_syntax = allow_python_syntax
            func.thread = thread
            self.requests[func.__req_name__] = func
            return
        return lambda x : self.request(x, name=name, auto_convert=auto_convert, allow_python_syntax=allow_python_syntax)
    
    def add_request(self, func : FunctionType, *, name : str = None, auto_convert : bool = False, allow_python_syntax : bool = True, thread : bool = False):
        """
        Method for adding requests.
        """
        func.__req_name__ = name or func.__name__
        func.auto_convert = auto_convert
        func.allow_python_syntax = allow_python_syntax
        func.thread = thread
        self.requests[func.__req_name__] = func
    
    def start(self, *, thread : bool = None, daemon_thread : bool = False, duration : Union[float, int, None] = None):
        """
        Method for starting the request handler.
        """
        if thread or (thread is None and self.uses_thread):
            self.uses_thread = True
            self.thread = StoppableThread(target=lambda : self.start(thread=False), daemon=daemon_thread)
            self.thread.start()
            return
        self.cloud_socket.listen()
        with self.cloud_socket.any_update:
            clients : list[tuple[CloudSocketConnection, str]] = []
            end_time = duration and (time.time() + duration)
            while (not end_time) or time.time() < end_time:
                success = self.cloud_socket.any_update.wait(30)
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
                        response = "No response."
                        try:
                            self.current_client = client
                            self.current_client_username = username
                            raw_sub_requests = [raw_request.strip() for raw_request in msg.split(";")]
                            sub_request_names = [re.match(r"\w+", raw_request).group() for raw_request in raw_sub_requests]
                            for req_name, raw_req in zip(sub_request_names, raw_sub_requests):
                                if re.match(r"\w+\(.*\)$", raw_req) and self.requests[req_name].allow_python_syntax:
                                    name, args, kwargs = parse_python_request(raw_req, req_name)
                                elif not re.match(r"\w+\(.*\)$", raw_req):
                                    name, args, kwargs = parse_normal_request(raw_req, req_name)
                                else:
                                    raise PermissionError("Python syntax is not allowed for this.")
                        except Exception:
                            response = "The command syntax was wrong."
                            warnings.warn("Received a request with an invalid syntax: \n"+traceback.format_exc(), RuntimeWarning)
                        else:
                            try:
                                self.execute_request(name, args=args, kwargs=kwargs, client=client)
                                response = None
                            except Exception:
                                response = "Something went wrong."
                                warnings.warn(f"Something went wrong with a request: {traceback.format_exc()}", RuntimeWarning)
                        if response:
                            client.send(response)
                except Exception:
                    warnings.warn(f"There was an uncaught error in the request handler: {traceback.format_exc()}", RuntimeWarning)
                
    
    def execute_request(self, name, *, args : Sequence[Any], kwargs : Mapping[str, Any], client : CloudSocketConnection) -> None:
        """
        Execute a request.
        """
        request_handling_function = self.requests[name]
        args, kwargs, return_converter = type_casting(func=request_handling_function, signature=inspect.signature(request_handling_function), args=args, kwargs=kwargs)
        def respond():
            try:
                response = str(return_converter(request_handling_function(*args, **kwargs)))
            except ErrorMessage as e:
                response = " ".join(e.args)
            client.send(response)
        if request_handling_function.thread:
            thread = StoppableThread(target=respond)
            thread.start()
            return
        respond()
    
    def stop(self):
        """
        Stop the request handler.
        """
        if not self.uses_thread:
            raise NotUsingAThread("Can't stop a request handler that is not using a thread.")
        self.thread.stop(StopRequestHandler)
        self.cloud_socket.stop()
        with self.cloud_socket.any_update:
            self.cloud_socket.any_update.notify_all()
        self.thread.join(5)
        
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

def type_casting(*, func : FunctionType, signature : inspect.Signature, args : tuple, kwargs : dict) -> tuple[tuple, dict, Callable]:
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
    return args, kwargs, return_callable

def parse_python_request(msg : str, name : str):
    """
    Parse a request in the format of a python function call.
    """
    parsed = ast.parse(msg).body[0].value
    assert parsed.func.id == name
    name = parsed.func.id
    args = [arg.value for arg in parsed.args]
    kwargs = {kwarg.arg: kwarg.value.value for kwarg in parsed.keywords}
    return name, args, kwargs

def parse_normal_request(msg : str, name : str):
    """
    Parse a request in the normal format.
    """
    i = iter(msg)
    STR = "str"
    NUM = "num"
    FLT = "float"
    ID = "id"
    MT = "space"
    mode = ID
    content = ""
    args = []
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
    return name, args, {}


class ErrorMessage(Exception):
    """
    Error with a message
    """


















