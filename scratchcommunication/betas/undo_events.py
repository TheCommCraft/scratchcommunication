"""
Undo the certain cloud events.
"""
from scratchcommunication import CloudConnection, Event

def register_undo(cloud : CloudConnection):
    """
    Decorator for registering a undo trigger. Your function should return True if the event should be undone.
    """ 
    def wrapper(func):
        old_values = cloud.values.copy()
        @cloud.on("set")
        def on_set(event : Event):
            if func(event):
                event.set_var(event.var, value=old_values[event.var], name_literal=True)
                return
            old_values[event.var] = event.value
    return wrapper