# scratchcommunication
A python module for communicating with scratch projects

# Installation

Run this in your commandline

```
pip install scratchcommunication
```

OR

Add this at the top of your python script

```python
import subprocess
subprocess.run("pip install --upgrade scratchcommunication", shell=True, capture_output=True)
```

# Creating a session

You can use the `scratchcommunication.session.Session` class to log into your account.

For this, you either need a session id or a password.

## Login using session id

```python
import scratchcommunication
session = scratchcommunication.Session("YOUR_USERNAME", session_id="YOUR_SESSIONID")
```

If you log in using your session id, you may not need your to supply your username.

## Login using password

```python
import scratchcommunication
session = scratchcommunication.Session.login("YOUR_USERNAME", "YOUR_PASSWORD")
```

I recommend using your session id instead of your password. 

## Access account data

Once you have logged into your account, you can access your account data.

```python
your_session_id = session.session_id
your_username = session.username
email = session.email
user_id = session.id
banned = session.banned
new_scratcher = session.new_scratcher
mute_status = session.mute_status
```

# Cloud Variables

## Connecting to Scratch Cloud Variables

You can connect to a scratch projects cloud variables using your `scratchcommunication.session.Session`

```python
cloud = session.create_cloudconnection(
    project_id = "Your project id here",
    quickaccess = False, # (Optional) Allows you to use the cloud connection as a Mapping for the cloud variables.
    reconnect = True, # (Optional) Allows the cloud connection to reconnect if it disconnects.
    receive_from_websocket = True, # (Optional) Creates a thread which receives cloud updates and allows for events.
    warning_type = ErrorInEventHandler, # (Optional) Determines what type of Warning will be used if there is an error in the event handler.
    daemon_thread = False # (Optional) Determines if the thread used for events will be daemon
)
```

OR

```python
cloud = scratchcommunication.CloudConnection(
    project_id = "Your project id here",
    session = session,
    **kwargs
)
```

## Connecting to Turbowarp Cloud Variables

To connect to Turbowarps Cloud Variables you can use the `scratchcommunication.cloud.TwCloudConnection` class

```python
tw_cloud = scratchcommunication.TwCloudConnection(
    project_id = "Your project id here", 
    username = "player1000", # (Optional)
    quickaccess = False, 
    reconnect = True, 
    receive_from_websocket = True, 
    warning_type = ErrorInEventHandler, 
    cloud_host = "wss://clouddata.turbowarp.org/", # (Optional) Changes the host used for cloud variables.
    accept_strs = False # (Optional) Allows you to set cloud variables to strings. Only works if cloud host allows it.
)
```

Or you could connect from your session

```python
tw_cloud = session.create_turbowarp_cloudconnection(
    project_id = "Your project id here",
    username = None, # (Optional) Will default to your username
    quickaccess = False, 
    reconnect = True, 
    receive_from_websocket = True, 
    warning_type = ErrorInEventHandler, 
    cloud_host = "wss://clouddata.turbowarp.org/", 
    accept_strs = False 
)
```

To shorten it a bit you can also use `scratchcommunication.session.Session.create_tw_cloudconnection` instead of `scratchcommunication.session.Session.create_turbowarp_cloudconnection`.

## Working with cloud variables

To set or get cloud variables you can use `scratchcommunication.cloud.CloudConnection.set_variable` and `scratchcommunication.cloud.CloudConnection.get_variable`.

```python
cloud.set_variable(
    name = "HIGHSCORE", # A cloud symbol will be added automatically if there isn't one
    value = 1000,
    name_literal = False # (Optional) Allows for setting a variable with a name without a cloud symbol
)
value = cloud.get_variable(
    name = "HIGHSCORE", 
    name_literal = False
)
```

Or if you enabled quickaccess you can use the object like a Mapping.

```python
cloud["HIGHSCORE"] = 1000

value = cloud["HIGHSCORE"]
```

For cloud events you can use the decorator `scratchcommunication.cloud.CloudConnection.on`

```python
@cloud.on("set") # Can be "set", "create", "delete", "connect" or "any"
def on_set(event):
    print(
        event.project_id, 
        event.name, # Variable name without cloud symbol
        event.var, # Variable name
        event.value, 
        event.type, # Event type
        event.project, # Cloud connection
        event.user,
        event.timestamp
    )
```

And if you want, you can also emit events yourself. (Those events will not be broadcast.)

```python
cloud.emit_event(event="custom_event_1", **entries)
# Or
cloud.emit_event(event=scratchcommunication.Event(type="custom_event_1", **entries))
```

And if you want to enable or disable quickaccess after you already created the connection, you can use `scratchcommunication.cloud.CloudConnection.enable_quickaccess` and `scratchcommunication.cloud.CloudConnection.disable_quickaccess`

```python
cloud.enable_quickaccess()
cloud.disable_quickaccess()
```

If you want to stop the background thread used for events and variable updates, you can use `scratchcommunication.cloud.CloudConnection.stop_thread`

```python
cloud.stop_thread()
```

If you set `daemon_thread` to `True` when creating the object, the background thread will terminate when your process ends.

# Cloud sockets

Cloud sockets (inspired by sockets) are connections from a scratch project to a python program where both sides can send data to one another and there is even the possibility to add security to the connection using RSA.

## Creating a cloud socket

To create a cloud socket you can use `scratchcommunication.session.Session.create_cloud_socket`.

```python
cloud_socket = session.create_cloud_socket(
    project_id = "Your project id here",
    packet_size = 220, # (Optional) I recommend leaving this value be if you only use Scratch and Turbowarp.
    cloudconnection_kwargs = None, # (Optional) Allows for adding keyword arguments for the Cloud Connection used in the cloud socket. Look at the documentation for Cloud Connection if you do not know which keyword arguments there are
    security = None # (Optional) Allows for a secure connection. Recommended. Look at Cloud Socket Security for more info.
)
```

You can also use Turbowarp for cloud sockets.

```python
cloud_socket = session.create_turbowarp_cloud_socket( # session.create_tw_cloud_socket also works here
    project_id = "Your project id here",
    packet_size = 220, # (Optional) I recommend leaving this value be if you only use Scratch and Turbowarp.
    cloudconnection_kwargs = None, # (Optional) Allows for adding keyword arguments for the Cloud Connection used in the cloud socket. Look at the documentation for Cloud Connection if you do not know which keyword arguments there are
    security = None # (Optional) Allows for a secure connection. Recommended. Look at Cloud Socket Security for more info.
)
```

[Cloud Socket Security](#cloud-socket-security)

In order for the cloud socket to work, you'll need to add the sprite from this [project](https://scratch.mit.edu/projects/884190099/) to yours. Be sure to check that all the variables starting with the cloud symbol are cloud variables and that their names stay as they are.

## Using a cloud socket

Once you have created a cloud socket you have to start it using `scratchcommunication.cloud_socket.CloudSocket.listen`

```python
cloud_socket.listen()
```

After you start the cloud socket you can wait for a new user using `scratchcommunication.cloud_socket.CloudSocket.accept`

```python
client, client_username = cloud_socket.accept()
```

When you have a client, you can send messages to them and receive messages.

```python
msg = client.recv()
client.send("Hello!")
```

**Your messages will be public and easy to fake in both direction unless you activate [security](#cloud-socket-security).**

In order to stop the cloud socket from running anymore you can you `scratchcommunication.cloud_socket.CloudSocket.stop`

```python
cloud_socket.stop()
```

## Cloud Socket Security

You might want to be able to send private data that only the designated recipient can read, but that is impossible unless you use asymmetric encryption or something similar. Fortunately for you, the hard work has already been done.

You will need to generate RSA keys for this. In order to do that, you can just use `scratchcommunication.security.RSAKeys.create_new_keys`.

```python
keys = scratchcommunication.security.RSAKeys.create_new_keys()
```

After you have generated your keys, you will want to store and load them. For storing your keys, you need to use `scratchcommunication.security.RSAKeys.keys` to find the values to store.

```python
print(keys.keys)
```

When you have stored the three integers displayed, you just need to load them whenever you start your cloud socket and put two of them in your project. **Never** reveal all of the keys unless you want to regenerate them.

```python
keys = scratchcommunication.security.RSAKeys((value_1, value_2, value_3))
print(keys.public_keys) # Put the resulting values into the corresponding variables in your Scratch project.
```

To use the keys in your cloud socket, you just need to pass them in as `security`.

```python
secure_cloud_socket = session.create_cloud_socket(
    project_id = "Your project id here", 
    security = keys
)
```

# Contact

If you have questions, want to propose new features or have found a bug, contact me [here](https://github.com/thecommcraft/scratchcommunication/issues)

# More coming soon
