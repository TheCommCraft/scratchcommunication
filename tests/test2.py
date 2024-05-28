import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scratchcommunication import Session, Event
import scratchcommunication
import json

USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
PROJECT_ID = 884190099#os.getenv("PROJECT_ID")

session = Session.login(USERNAME, PASSWORD)
cloud = session.create_cloudconnection(PROJECT_ID)
client = scratchcommunication.cloudrequests.RequestHandler(cloud_socket=cloud, uses_thread=True)

@client.request(name="test", auto_convert=True, allow_python_syntax=True, thread=False)
def test_cmd(abc1 : int = None, abc2 : float = None) -> json.dumps:
    return str(abc1) + str(abc2)

input()
cloud.stop_thread()
exit()
