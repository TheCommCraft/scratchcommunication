import os, sys, json
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scratchcommunication import Session

def get_session() -> Session:
    with open(os.path.join(os.path.dirname(__file__), "cached.txt")) as f:
        try:
            data = json.load(f)
        except Exception:
            data = {}
        SESSION_ID = data.get("SESSION_ID")
        XTOKEN = data.get("XTOKEN")
    USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
    
    try:
        session = Session(username=USERNAME, session_id=SESSION_ID, xtoken=XTOKEN)
    except Exception:
        pass
    else:
        return session

    session = Session.login(USERNAME, PASSWORD)
    data = {"SESSION_ID": session.session_id, "XTOKEN": session.xtoken}
    with open(os.path.join(os.path.dirname(__file__), "cached.txt")) as f:
        json.dump(data, f)
    return session