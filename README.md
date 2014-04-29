Home Assistant
==============

Home Assistant is a home automation platform running on Python 3. It provides modules that observe and trigger actors to do various tasks.

It is currently able to do the following things:
 * Track if devices are home by monitoring connected devices to a wireless router (currently supporting modern Netgear routers or routers running Tomato firmware)
 * Track and control lights
 * Track and control WeMo switches
 * Track and control Chromecasts
 * Turn on the lights when people get home when the sun is setting or has set
 * Slowly turn on the lights to compensate for light loss when the sun sets and people are home
 * Turn off lights and connected devices when everybody leaves the house
 * Download files to the host machine
 * Open a url in the default browser at the host machine
 * Simulate key presses on the host for Play/Pause, Next track, Prev track, Volume up, Volume Down
 * Controllable via a REST API and web interface
 * Support for remoting Home Assistant instances through a Python API
 * Android Tasker project to control Home Assistant from your phone and report charging state.

![screenshot-states](https://raw.github.com/balloob/home-assistant/master/docs/states.png)

Current compatible devices:
 * [WeMo switches](http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/)
 * [Philips Hue](http://meethue.com)
 * [Google Chromecast](http://www.google.com/intl/en/chrome/devices/chromecast)
 * Wireless router running [Tomato firmware](http://www.polarcloud.com/tomato)
 * Netgear wireless routers (tested with R6300)

The system is built modular so support for other devices or actions can be implemented easily.

Installation instructions
-------------------------
* The core depends on [PyEphem](http://rhodesmill.org/pyephem/) and [Requests](http://python-requests.org). Depending on the components you would like to use you will need [PHue](https://github.com/studioimaginaire/phue) for Philips Hue support and [PyChromecast](https://github.com/balloob/pychromecast) for Chromecast support. Install these using `pip install pyephem requests phue pychromecast`.
* Clone the repository and pull in the submodules `git clone --recursive https://github.com/balloob/home-assistant.git`
* Copy home-assistant.conf.default to home-assistant.conf and adjust the config values to match your setup.
  * For Tomato you will have to not only setup your host, username and password but also a http_id. The http_id can be retrieved by going to the admin console of your router, view the source of any of the pages and search for `http_id`.
* If you want to use Hue, setup PHue by running `python -m phue --host HUE_BRIDGE_IP_ADDRESS` from the commandline and follow the instructions.
* While running the script it will create and maintain a file called `known_devices.csv` which will contain the detected devices. Adjust the track variable for the devices you want the script to act on and restart the script or call the service `device_tracker/reload_devices_csv`.

Done. Start it now by running `python start.py`

Architecture
------------
The core of Home Assistant exists of three parts; an EventBus for firing events, a StateMachine that keeps track of the state of things and a ServiceRegistry to manage services.

![home assistant architecture](https://raw.github.com/balloob/home-assistant/master/docs/architecture.png)

For example to control the lights there are two components. One is the device_tracker that polls the wireless router for connected devices and updates the state of the tracked devices in the State Machine to be either 'Home' or 'Not Home'.

When a state is changed a state_changed event is fired for which the device_sun_light_trigger component is listening. Based on the new state of the device combined with the state of the sun it will decide if it should turn the lights on or off:

    In the event that the state of device 'Paulus Nexus 5' changes to the 'Home' state:
      If the sun has set and the lights are not on:
        Turn on the lights
    
    In the event that the combined state of all tracked devices changes to 'Not Home':
      If the lights are on:
        Turn off the lights
        
    In the event of the sun setting:
      If the lights are off and the combined state of all tracked device equals 'Home':
        Turn on the lights

By using the Bus as a central communication hub between components it is easy to replace components or add functionality. For example if you would want to change the way devices are detected you only have to write a component that updates the device states in the State Machine.

### Components

**sun**
Tracks the state of the sun and when the next sun rising and setting will occur.
Depends on: latitude and longitude
Action: maintains state of `weather.sun` including attributes `next_rising` and `next_setting`

**device_tracker**
Keeps track of which devices are currently home.
Action: sets the state per device and maintains a combined state called `all_devices`. Keeps track of known devices in the file `known_devices.csv`. 

**Light**
Keeps track which lights are turned on and can control the lights.

**WeMo**
Keeps track which WeMo switches are in the network and allows you to control them.

**device_sun_light_trigger**
Turns lights on or off using a light control component based on state of the sun and devices that are home.
Depends on: light control, track_sun, DeviceTracker
Action: 
 * Turns lights off when all devices leave home. 
 * Turns lights on when a device is home while sun is setting. 
 * Turns lights on when a device gets home after sun set.

Registers services `light_control/turn_light_on` and `light_control/turn_light_off` to turn a or all lights on or off.

Optional service data:
  - `light_id` - only act on specific light. Else targets all.
  - `transition_seconds` - seconds to take to swithc to new state.

**chromecast**
Registers three services to start playing YouTube video's on the ChromeCast.

Service `chromecast/play_youtube_video` starts playing the specified video on the YouTube app on the ChromeCast. Specify video using `video` in service_data.

Service `chromecast/start_fireplace` will start a YouTube movie simulating a fireplace and the `chromecast/start_epic_sax` service will start playing Epic Sax Guy 10h version.

**media_buttons**
Registers services that will simulate key presses on the keyboard. It currently offers the following Buttons as a Service (BaaS): `keyboard/volume_up`, `keyboard/volume_down` and `keyboard/media_play_pause`
This actor depends on: PyUserInput

**downloader**
Registers service `downloader/download_file` that will download files. File to download is specified in the `url` field in the service data.

**browser**
Registers service `browser/browse_url` that opens `url` as specified in event_data in the system default browser.

### Multiple connected instances

Home Assistant supports running multiple synchronzied instances using a master-slave model. Slaves forward all local events fired and states set to the master instance which will then replicate it to each slave.

Because each slave maintains it's own ServiceRegistry it is possible to have multiple slaves respond to one service call.

![home assistant master-slave architecture](https://raw.github.com/balloob/home-assistant/master/docs/architecture-remote.png)

Web interface and API
---------------------
Home Assistent runs a webserver accessible on port 8123. 

  * At http://localhost:8123/ it will provide a debug interface showing the current state of the system and an overview of registered services.
  * At http://localhost:8123/api/ it provides a password protected API.

A screenshot of the debug interface:
![screenshot-debug-interface](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-debug-interface.png)

In the package `homeassistant.remote` a Python API on top of the HTTP API can be found.

All API calls have to be accompanied by an 'api_password' parameter (as specified in `home-assistant.conf`) and will
return JSON encoded objects. If successful calls will return status code 200 or 201.

Other status codes that can occur are:
 - 400 (Bad Request)
 - 401 (Unauthorized)
 - 404 (Not Found)
 - 405 (Method not allowed)

The api supports the following actions:

**/api/events - GET**<br>
Returns a dict with as keys the events and as value the number of listeners.

```json
{
    "event_listeners": {
      "state_changed": 5,
      "time_changed": 2
    }  
}
```

**/api/services - GET**<br>
Returns a dict with as keys the domain and as value a list of published services.

```json
{
    "services": {
      "browser": [
          "browse_url"
      ],
      "keyboard": [
          "volume_up",
          "volume_down"
      ]
    }  
}
```

**/api/states - GET**<br>
Returns a dict with as keys the entity_ids and as value the state.

```json
{
    "sun.sun": {
        "attributes": {
            "next_rising": "07:04:15 29-10-2013", 
            "next_setting": "18:00:31 29-10-2013"
        }, 
        "entity_id": "sun.sun", 
        "last_changed": "23:24:33 28-10-2013", 
        "state": "below_horizon"
    },
    "process.Dropbox": {
        "attributes": {}, 
        "entity_id": "process.Dropbox", 
        "last_changed": "23:24:33 28-10-2013", 
        "state": "on"
    }
}
```

**/api/states/&lt;entity_id>** - GET<br>
Returns the current state from an entity

```json
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013", 
        "next_setting": "18:00:31 29-10-2013"
    }, 
    "entity_id": "sun.sun", 
    "last_changed": "23:24:33 28-10-2013", 
    "state": "below_horizon"
}
```

**/api/states/&lt;entity_id>** - POST<br>
Updates the current state of an entity. Returns status code 201 if successful with location header of updated resource and the new state in the body.<br>
parameter: new_state - string<br>
optional parameter: attributes - JSON encoded object

```json
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013", 
        "next_setting": "18:00:31 29-10-2013"
    }, 
    "entity_id": "weather.sun", 
    "last_changed": "23:24:33 28-10-2013", 
    "state": "below_horizon"
}
```

**/api/events/&lt;event_type>** - POST<br>
Fires an event with event_type<br>
optional parameter: event_data - JSON encoded object

```json
{
    "message": "Event download_file fired."
}
```

**/api/services/&lt;domain>/&lt;service>** - POST<br>
Calls a service within a specific domain.<br>
optional parameter: service_data - JSON encoded object

```json
{
    "message": "Service keyboard/volume_up called."
}
```

**/api/event_forwarding** - POST<br>
Setup event forwarding to another Home Assistant instance.<br>
parameter: host - string<br>
parameter: api_password - string<br>
optional parameter: port - int<br>

```json
{
    "message": "Event forwarding setup."
}
```

**/api/event_forwarding** - DELETE<br>
Cancel event forwarding to another Home Assistant instance.<br>
parameter: host - string<br>
optional parameter: port - int<br>

If your client does not support DELETE HTTP requests you can add an optional attribute _METHOD and set its value to DELETE.

```json
{
    "message": "Event forwarding cancelled."
}
```

Android remote control
----------------------

An app has been built using [Tasker for Android](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) that:

 * Provides buttons to control the lights and the chromecast
 * Reports the charging state and battery level of the phone

The [APK](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.apk) and [Tasker project XML](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.prj.xml) can be found in [/android-tasker/](https://github.com/balloob/home-assistant/tree/master/android-tasker)

![screenshot-android-tasker.jpg](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-android-tasker.png)
