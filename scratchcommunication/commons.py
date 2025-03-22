from enum import Enum, auto

_headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36",
    "x-csrftoken": "a",
    "x-requested-with": "XMLHttpRequest",
    "referer": "https://scratch.mit.edu",
}

_cookies = {
    "scratchcsrftoken" : "a",
    "scratchlanguage" : "en",
    "scratchpolicyseen": "true",
    "accept": "application/json",
    "Content-Type": "application/json",
}

def get_headers():
    return _headers.copy()

def get_cookies():
    return _cookies.copy()

class Browser(Enum):
    FIREFOX = auto()
    CHROME = auto()
    EDGE = auto()
    SAFARI = auto()
    CHROMIUM = auto()
    EDGE_DEV = auto()
    VIVALDI = auto()
    ANY = auto()
