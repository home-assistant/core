Home Assistant
==============

Home Assistant automatically switches the lights on and off based on nearby devices and the position of the sun.

It is currently able to do the following things:
 * Turn on the lights when one of the tracked devices is nearby
 * Turn off the lights when everybody leaves
 * Turn on the lights when the sun sets and one of the tracked devices is home

It currently works with any wireless router with [Tomato firmware](http://www.polarcloud.com/tomato) in combination with [Philips Hue](http://meethue.com). The system is built modular so support for other wireless routers or other actions can be implemented easily.

Installation instructions
-------------------------

* install python modules [python-dateutil](http://labix.org/python-dateutil), [PyEphem](http://rhodesmill.org/pyephem/), [Requests](http://python-requests.org) and [PHue](https://github.com/studioimaginaire/phue): `pip install python-dateutil pyephem requests phue`
* Clone the repository `git clone https://github.com/balloob/home-assistant.git`.
* Copy home-assistant.conf.default to home-assistant.conf and adjust the config values to match your setup.
  * For Tomato you will have to not only setup your host, username and password but also a http_id. The http_id can be retrieved by going to the admin console of your router, view the source of any of the pages and search for `http_id`.
* Setup PHue by running `python -m phue --host HUE_BRIDGE_IP_ADDRESS` from the commandline.
* The first time the script will start it will create a file called `known_devices.csv` which will contain the detected devices. Adjust the track variable for the devices you want the script to act on and restart the script.

Done. Start it now by running `python start.py`

Web interface and API
---------------------
Home Assistent runs a webserver accessible on port 8123. At http://localhost:8123/ it will provide a debug interface showing the current state of the system. At http://localhost:8123/api/ it provides a password protected API so it can be controlled from other devices through HTTP POST requests. 

A screenshot of the debug interface (battery and charging states are controlled by my phone):
![screenshot-debug-interface](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-debug-interface.png)

To interface with the API requests should include the parameter api_password which matches the api_password in home-assistant.conf.

The following API commands are currently supported:

    /api/state/change - POST
    parameter: api_password - string
    parameter: category - string
    parameter: new_state - string
    Changes category 'category' to 'new_state'
    It is possible to sent multiple values for category and new_state.
    If the number of values for category and new_state do not match only
    combinations where both values are supplied will be set.
    
    /api/event/fire - POST
    parameter: api_password - string
    parameter: event_name - string
    parameter: event_data - object encoded as JSON string (optional)
    Fires an 'event_name' event containing data from 'event_data'

Android remote control
----------------------

Using [Tasker for Android](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) I built an Android app that:

 * provides buttons to control the lights and the chromecast
 * sent updates every 30 minutes on the battery status
 * sent updates when the phone is being charged via usb or wireless 

The [APK](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.apk) and [Tasker project XML](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.prj.xml) can be found in [/android-tasker/](https://github.com/balloob/home-assistant/tree/master/android-taster)

![screenshot-android-tasker.jpg](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-android-tasker.png)

Architecture
---------------------------

Home Assistent has been built from the ground up with extensibility and modularity in mind. It is easy to swap in a different device tracker that polls another wireless router for example. 

The beating heart of Home Assistant is an event bus. Different modules are able to fire and listen for specific events. On top of this is a state machine that allows modules to track the state of different things. For example each device that is being tracked will have a state of either 'Home' or 'Not Home'. 

This allows us to implement simple business rules to easily customize or extend functionality: 

    In the event that the state of device 'Paulus Nexus 4' changes to the 'Home' state:
      If the sun has set and the lights are not on:
        Turn on the lights
    
    In the event that the combined state of all tracked devices changes to 'Not Home':
      If the lights are on:
        Turn off the lights
        
    In the event of the sun setting:
      If the lights are off and the combined state of all tracked device equals 'Home':
        Turn on the lights

These rules are currently implemented in the file [actors.py](https://github.com/balloob/home-assistant/blob/master/homeassistant/actors.py).
