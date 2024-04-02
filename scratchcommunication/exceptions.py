class InvalidValueError(ValueError):
    pass

class QuickAccessDisabledError(Exception):
    pass

class NotSupported(Exception):
    pass

class ErrorInEventHandler(RuntimeWarning):
    pass

class ErrorInCloudSocket(RuntimeWarning):
    pass

class StopException(BaseException):
    pass

class EventExpiredError(Exception):
    pass
