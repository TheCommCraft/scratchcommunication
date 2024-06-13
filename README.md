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
# You can also supply your XToken if it cannot be found using xtoken="YOUR_XTOKEN
```

If you log in using your session id, you may not need your to supply your username.

## Login using password

```python
import scratchcommunication
session = scratchcommunication.Session.login("YOUR_USERNAME", "YOUR_PASSWORD")
```

I recommend using your session id instead of your password. 

## Login from browser

This will login using cookies from your browser. It only works if you have that browser installed and if you are logged in.

```python
import scratchcommunication
session = scratchcommunication.Session.from_browser(scratchcommunication.ANY)
```

You can choose from these browsers:

FIREFOX
CHROME
EDGE
SAFARI
CHROMIUM
EDGE_DEV
VIVALDI
ANY

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
    contact_info = "Your contact info", # Specify some contact info. Turbowarp will block your connection otherwise.
    project_id = "Your project id here", 
    username = "player1000", # (Optional)
    quickaccess = False, 
    reconnect = True, 
    receive_from_websocket = True, 
    warning_type = ErrorInEventHandler, 
    cloud_host = "wss://clouddata.turbowarp.org/", # (Optional) Changes the host used for cloud variables.
    accept_strs = False, # (Optional) Allows you to set cloud variables to strings. Only works if cloud host allows it.
    keep_all_events = False # (Optional) Allows you to disable automatic garbage disposal of events. Events can still be manually disposed of. Unrecommended because it will slowly but surely fill up a lot of memory if events aren't disposed of.
)
```

Or you could connect from your session

```python
tw_cloud = session.create_turbowarp_cloudconnection(
    contact_info = "Your contact info",
    project_id = "Your project id here",
    username = None, # (Optional) Will default to your username
    quickaccess = False, 
    reconnect = True, 
    receive_from_websocket = True, 
    warning_type = ErrorInEventHandler, 
    cloud_host = "wss://clouddata.turbowarp.org/", 
    accept_strs = False,
    keep_all_events = False,
    allow_no_certificate = False # (Optional) Put to True if the SSL Certificate fails.
)
```

**Warning: You need to add sufficient contact_info for your turbowarp connection or it might not work!**

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

You can also manually dispose of events (which normally happens automatically).

```python
cloud.garbage_disposal_of_events(
    force_disposal = False # (Optional) Is needed to be True if automatic garbage disposal is disabled.
)
```

If you set `daemon_thread` to `True` when creating the object, the background thread will terminate when your process ends.

# Cloud requests

Cloud requests are based on [cloud sockets](#cloud-sockets) and allow you to have your project send requests to your server which it automatically responds to. You'll need to put the first sprite from this [project](https://scratch.mit.edu/projects/884190099/) in your project for cloud requests to work.

## Creating a cloud requests handler

To use cloud requests, you first need to create a [cloud socket](#cloud-sockets) to your project and then a cloud requests handler which uses it to communicate to your Scratch project.

```python
cloud_requests = scratchcommunication.RequestHandler(
    cloud_socket = cloud_socket, # The cloud socket to communicate with the project
    uses_thread = False # (Optional) Determines if the cloud requests handler uses a thread for execution normally.
)
```

## Create requests

You can use the method `add_request` to add a request or the `request` wrapper.

```python
cloud_requests.add_request(
    your_function, # Replace this with the function you want to use.
    name = None, # (Optional) Change the name of the function.
    auto_convert = False, # (Optional) Whether to automatically convert all arguments and return values related to the request based on its type annotations
    allow_python_syntax = True, # (Optional) Whether to allow the frontend requests in python syntax (e.g. func(arg1, arg2, kwarg1=val1, kwarg2=val2, ...)). This has no backsides.
    thread = False # (Optional) Determines if the request's function and response should be in a different thread. This might cost a lot of processing power.  
)

# OR

@cloud_requests.request
def func(arg1, arg2):
    pass # Write your own function

# OR

@cloud_requests.request(name=None, auto_convert=False, allow_python_syntax=True, thread=False)
def func(arg1, arg2):
    pass # Write your own function
```

## Starting the cloud requests handler

Start the cloud requests handler using the `start` method.

```python
cloud_requests.start(
    thread = None, # (Optional) Whether to use a thread; If None then it defaults to the used_thread value used at creation of the cloud requests handler
    daemon_thread = False, # (Optional) Whether the thread is daemon
    duration = None # (Optional) How long to run the cloud requests
)
```

## Stopping the cloud requests handler

Stop the cloud requests handler using the `stop` method. (Only if the cloud requests handler is running in a thread)

```python
cloud_requests.stop()
```

## Encrypted data transmission

For making the data transmission in your cloud request handler secret, you need to make the underlying cloud socket secure.

See [Cloud Socket Security](#cloud-socket-security) for this.

## Client side

If you haven't already, you'll need to put the first sprite from this [project](https://scratch.mit.edu/projects/884190099/) in your project for cloud requests to work.

You'll always first need to connect on your client side for your messages to work. This is done using the "[cloud socket] connect securely" or "[cloud socket] connect insecurely" blocks. 

When you are connected, you can use the block "[cloud requests] initiate new request (%s)" to initiate a new request with its name. The name must not contain spaces. When you have initiated a new request, you can add arguments to the request by using the "[cloud requests] add argument (%s)" block. When you are done creating the request, you can use the block "[cloud requests] send iniated request" to send it and wait for the response.

The received data will be in the variable "[cloud] reception". You can change the timeout using the "# TIMEOUT" variable (If you don't need a timeout, just let it stay). You can also change the packet size using the "# PACKET SIZE" variable, but I would advise against this if you are not using turbowarp.

# Cloud sockets

Cloud sockets (inspired by sockets) are connections from a scratch project to a python program where both sides can send data to one another and there is even the possibility to add security to the connection using RSA.

Warning: Cloud sockets are low level. They allow you to do more but are more difficult to use. You shouldn't use them directly. You might want to use them in [cloud requests](#cloud-requests) instead.

## Creating a cloud socket

To create a cloud socket you can use `scratchcommunication.session.Session.create_cloud_socket`.

```python
cloud_socket = session.create_cloud_socket(
    project_id = "Your project id here",
    packet_size = 220, # (Optional) I recommend leaving this value be if you only use Scratch and Turbowarp.
    cloudconnection_kwargs = None, # (Optional) Allows for adding keyword arguments for the Cloud Connection used in the cloud socket. Look at the documentation for Cloud Connection if you do not know which keyword arguments there are
    security = None, # (Optional) Allows for a secure connection. Recommended. Look at Cloud Socket Security for more info.
    allow_no_certificate = False # (Optional) Put to True if the SSL Certificate fails.
)
```

You can also use Turbowarp for cloud sockets.

```python
cloud_socket = session.create_turbowarp_cloud_socket( # session.create_tw_cloud_socket also works here
    contact_info = "Your contact info",
    project_id = "Your project id here",
    packet_size = 220, # (Optional) I recommend leaving this value be if you only use Scratch and Turbowarp.
    cloudconnection_kwargs = None, # (Optional) Allows for adding keyword arguments for the Cloud Connection used in the cloud socket. Look at the documentation for Cloud Connection if you do not know which keyword arguments there are
    security = None, # (Optional) Allows for a secure connection. Recommended. Look at Cloud Socket Security for more info.
    allow_no_certificate = False
)
```

[Cloud Socket Security](#cloud-socket-security)

In order for the cloud socket to work, you'll need to add the sprite from this [project](https://scratch.mit.edu/projects/884190099/) to yours. Be sure to check that all the variables starting with the cloud symbol are cloud variables and that their names stay as they are.

## Using a cloud socket

Once you have created a cloud socket you have to start it using `scratchcommunication.cloud_socket.CloudSocket.listen` and you can also put it in a with statement, which makes the cloud socket shut down automatically when the code is done executing.

```python
cloud_socket.listen()

# OR

with cloud_socket.listen():
    ... # Your code here
```



After you start the cloud socket you can wait for a new user using `scratchcommunication.cloud_socket.CloudSocket.accept`

```python
client, client_username = cloud_socket.accept(
    timeout = 10 # (Optional) 
)
```

When you have a client, you can send messages to them and receive messages.

```python
msg = client.recv(
    timeout = 10 # (Optional)
)
client.send("Hello!")
```

**Your messages will be public and easy to fake in both direction unless you activate [security](#cloud-socket-security).**

In order to stop the cloud socket from running anymore you can use `scratchcommunication.cloud_socket.CloudSocket.stop`

```python
cloud_socket.stop()
```

## Client side

If you haven't already, you'll need to put the first sprite from this [project](https://scratch.mit.edu/projects/884190099/) in your project for cloud socket to work.

You'll always first need to connect on your client side for your messages to work. This is done using the "[cloud socket] connect securely" or "[cloud socket] connect insecurely" blocks. 

Afterwards, you can use the "[cloud socket] send (%s)" block and the "[cloud socket] recv" block. 

The received data will be in the variable "[cloud] reception". You can change the timeout using the "# TIMEOUT" variable (If you don't need a timeout, just let it stay). You can also change the packet size using the "# PACKET SIZE" variable, but I would advise against this if you are not using turbowarp.

## Cloud Socket Security

You might want to be able to send private data that only the designated recipient can read, but that is impossible unless you use asymmetric encryption or something similar. Fortunately for you, the hard work has already been done.

You will need to generate a Security object for this. In order to do that, you can just use `scratchcommunication.security.Security.generate`.

```python
security = scratchcommunication.security.Security.generate()
```

After you have generated your keys, you will want to store and load them. For storing your keys, you need to use `scratchcommunication.security.Security.to_string` to find the data to store.

```python
string_representation_of_security = security.to_string()
print(string_representation_of_security)
```

When you have stored the string displayed, you just need to load it whenever you start your cloud socket using some code similar to this:

```python
security = scratchcommunication.security.Security.from_string(string_representation_of_security)
```

Next, you need to look at `security.public_data`. 

```python
print(security.public_data)
```

It will be a dictionary with the keys being variable names and the values being the value you need to set them to in your project.

To use the security object in your cloud socket, you just need to pass it in as `security`.

```python
secure_cloud_socket = session.create_cloud_socket(
    project_id = "Your project id here", 
    security = security
)
```

### Important security notice

**NEVER** make the string representation of the security or any other data relating to the security public except for the aforementioned public data, because making any of the secret data public will make all transmission insecure again.

# Contact

If you have questions, want to propose new features or have found a bug, contact me [here](https://github.com/thecommcraft/scratchcommunication/issues)

# Credits

A lot of frontend cryptography by @Retr0id on Scratch (https://scratch.mit.edu/users/Retr0id)

Inspiration by @TimMcCool

Everything else by me (I think)

# More coming soon
