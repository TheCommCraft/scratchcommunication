import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scratchcommunication import Session, Event
import scratchcommunication

USERNAME, PASSWORD = os.getenv("SCRATCH_USERNAME"), os.getenv("SCRATCH_PASSWORD")
PROJECT_ID = os.getenv("PROJECT_ID")

session = Session.login(USERNAME, PASSWORD)
cloud = session.create_cloudconnection(PROJECT_ID)

donit = set()

@cloud.on("set")
def on_set(event : Event):
    if event.value in donit:
        try:
            print(event.timestamp, event.project.processed_events[-2].timestamp)
        except KeyError:
            print(event.project.event_order)
            print(event.project.event_order[event.value])
            print(event.project.event_order[event.value][event])
        return
    donit.add(event.value)
    cloud.set_variable(name=event.name, value=event.value)

input()
cloud.stop_thread()
exit()
