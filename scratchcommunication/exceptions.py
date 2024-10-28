class QuickAccessDisabledError(Exception):
    pass

class NotSupported(Exception):
    pass

class ErrorInEventHandler(RuntimeWarning):
    pass

class ErrorInCloudSocket(RuntimeWarning):
    pass

class StopException(SystemExit):
    pass

class EventExpiredError(Exception):
    pass

class LoginFailure(Exception):
    pass