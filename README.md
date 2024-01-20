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
    warning_type = ErrorInEventHandler # (Optional) Determines what type of Warning will be used if there is an error in the event handler.
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

```python
tw_cloud = scratchcommunication.TwCloudConnection(
    project_id = "Your project id here", 
    username = "player1000", 
    quickaccess = False, 
    reconnect = True, 
    receive_from_websocket = True, 
    cloud_host = "wss://clouddata.turbowarp.org/", # (Optional) Changes the host used for cloud variables.
    accept_strs = False # (Optional) Allows you to set cloud variables to strings. Only works if cloud host allows it.
)
```

## More coming soon!