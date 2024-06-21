import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from manage_login import get_session
from scratchcommunication import Session, CloudSocket, Sky
import scratchcommunication
import json

USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
PROJECT_ID = 884190099#os.getenv("PROJECT_ID")

security = scratchcommunication.security.Security.from_string(os.getenv("SCRATCH_SECURITY"))#scratchcommunication.security.Security.generate()
input(f"The public data is: \"{security.public_data}\". The string representation of the keys is: \"{security.to_string()}\". Press enter to continue")

session = get_session()
cloud_connection = Sky(session.create_cloudconnection(PROJECT_ID))
cloud = CloudSocket(cloud=cloud_connection, security=security)
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
