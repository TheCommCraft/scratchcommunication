import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from manage_login import get_session
from scratchcommunication import Session
import scratchcommunication
import json

USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
PROJECT_ID = 884190099#os.getenv("PROJECT_ID")

session = get_session()
cloud = session.create_tw_cloud_socket(PROJECT_ID, contact_info="TheCommCraft on github, scratch or discord")
client = scratchcommunication.cloudrequests.RequestHandler(cloud_socket=cloud, uses_thread=True)

@client.request(name="test", auto_convert=True, allow_python_syntax=True, thread=False)
def test_cmd(abc1 : int = None, abc2 : float = None) -> json.dumps:
    print(abc1, abc2)
    return {"abc1": abc1, "abc2": abc2}

try:
    client.start()
    print("running")
    input()
finally:
    print("stopping")
    client.stop()
    print("stopped")
    exit()
