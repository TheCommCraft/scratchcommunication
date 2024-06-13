import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scratchcommunication#
from dotenv import load_dotenv

load_dotenv()

USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
PROJECT_ID = os.getenv("PROJECT_ID")


session = scratchcommunication.Session.login(USERNAME, PASSWORD)

security = scratchcommunication.security.Security.from_string(os.getenv("SCRATCH_SECURITY"))

cloud_socket = session.create_cloud_socket(
    project_id = "884190099",
    security = security
)

with cloud_socket.listen():
    while True:
        try:
            client, client_username = cloud_socket.accept()
        except TimeoutError:
            continue
        print(client_username + " connected!")
        
        client.send("Hello client!")