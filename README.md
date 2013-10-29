Home Assistant
==============

Home Assistant provides a platform for home automation. It does so by having modules that observe and trigger actors to do various tasks.

It is currently able to do the following things:
 * Track if devices are home by monitoring connected devices to a wireless router
 * Turn on the lights when people get home when it is dark
 * Slowly turn on the lights to compensate for light loss when the sun sets
 * Turn off the lights when everybody leaves the house
 * Start YouTube video's on the Chromecast
 * Download files to the host
 * Open a url in the default browser on the host

It currently works with any wireless router with [Tomato firmware](http://www.polarcloud.com/tomato) in combination with [Philips Hue](http://meethue.com) and the [Google Chromecast](http://www.google.com/intl/en/chrome/devices/chromecast). The system is built modular so support for other wireless routers, other devices or actions can be implemented easily.

Installation instructions
-------------------------
* Install python modules [PyEphem](http://rhodesmill.org/pyephem/), [Requests](http://python-requests.org) and [PHue](https://github.com/studioimaginaire/phue): `pip install pyephem requests phue`
* Clone the repository and pull in the submodules `git clone --recursive https://github.com/balloob/home-assistant.git`
* Copy home-assistant.conf.default to home-assistant.conf and adjust the config values to match your setup.
  * For Tomato you will have to not only setup your host, username and password but also a http_id. The http_id can be retrieved by going to the admin console of your router, view the source of any of the pages and search for `http_id`.
* Setup PHue by running `python -m phue --host HUE_BRIDGE_IP_ADDRESS` from the commandline.
* The first time the script will start it will create a file called `known_devices.csv` which will contain the detected devices. Adjust the track variable for the devices you want the script to act on and restart the script.

Done. Start it now by running `python start.py`

Web interface and API
---------------------
Home Assistent runs a webserver accessible on port 8123. 

  * At http://localhost:8123/ it will provide a debug interface showing the current state of the system.
  * At http://localhost:8123/api/ it provides a password protected API.

A screenshot of the debug interface:
![screenshot-debug-interface](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-debug-interface.png)

All API calls have to be accompanied by an 'api_password' parameter (as specified in `home-assistant.conf`) and will
return JSON encoded objects. If successful calls will return status code 200 or 201.

Other status codes that can occur are:
 - 400 (Bad Request)
 - 401 (Unauthorized)
 - 404 (Not Found)
 - 405 (Method not allowed)

The api supports the following actions:

**/api/states - GET**<br>
Returns a list of categories for which a state is available

```json
{
    "categories": [
        "Paulus_Nexus_4", 
        "weather.sun", 
        "all_devices"
    ]
}
```

**/api/states/&lt;category>** - GET<br>
Returns the current state from a category

```json
{
    "attributes": {
        "next_rising": "07:04:15 29-10-2013", 
        "next_setting": "18:00:31 29-10-2013"
    }, 
    "category": "weather.sun", 
    "last_changed": "23:24:33 28-10-2013", 
    "state": "below_horizon"
}
```

**/api/states/&lt;category>** - POST<br>
Updates the current state of a category. Returns status code 201 if successful with location header of updated resource.<br>
parameter: new_state - string<br>
optional parameter: attributes - JSON encoded object

**/api/events/&lt;event_type>** - POST<br>
Fires an event with event_type<br>
optional parameter: event_data - JSON encoded object

```json
{
    "message": "Event download_file fired."
}
```

Android remote control
----------------------

An app has been built using [Tasker for Android](https://play.google.com/store/apps/details?id=net.dinglisch.android.taskerm) that:

 * Provides buttons to control the lights and the chromecast
 * Tracks the charging state and battery level for each phone

The [APK](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.apk) and [Tasker project XML](https://raw.github.com/balloob/home-assistant/master/android-tasker/Home_Assistant.prj.xml) can be found in [/android-tasker/](https://github.com/balloob/home-assistant/tree/master/android-tasker)

![screenshot-android-tasker.jpg](https://raw.github.com/balloob/home-assistant/master/docs/screenshot-android-tasker.png)

Architecture
------------
Home Assistent has been built from the ground up with extensibility and modularity in mind. It is easy to swap in a different device tracker that polls another wireless router for example. 

![screenshot-android-tasker.jpg](https://raw.github.com/balloob/home-assistant/master/docs/architecture.png)

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

### Supported observers

**track_sun**
Tracks the state of the sun and when the next sun rising and setting will occur.
Depends on: latitude and longitude
Action: maintains state of `weather.sun` including attributes `next_rising` and `next_setting`

**TomatoDeviceScanner**
A device scanner that scans a Tomato-based router and retrieves currently connected devices. To be used by `DeviceTracker`.
Depends on: host, username, password and http_id to login to Tomato Router.

**DeviceTracker**
Keeps track of which devices are currently home.
Depends on: a device scanner
Action: sets the state per device and maintains a combined state called `all_devices`. Keeps track of known devices in the file `known_devices.csv`.

### Supported actors

**HueLightControl**
A light control for controlling the Philips Hue lights.

**LightTrigger**
Turns lights on or off using supplied light control based on state of the sun and devices that are home.
Depends on: light control, track_sun, DeviceTracker
Action: 
 * Turns lights off when all devices leave home. 
 * Turns lights on when a device is home while sun is setting. 
 * Turns lights on when a device gets home after sun set.

Listens for events `turn_light_on` and `turn_light_off`:
Turn a or all lights on or off

Optional event_data:
  - `light_id` - only act on specific light. Else targets all.
  - `transition_seconds` - seconds to take to swithc to new state.

**file_downloader**
Listen for `download_file` events to start downloading from the `url` specified in event_data.

**webbrowser**
Listen for `browse_url` events and opens a browser with the `url` specified in event_data.

**chromecast**
Listen for `chromecast.play_youtube_video` events and starts playing the specified video on the YouTube app on the ChromeCast. Specify video using `video` in event_data.

Also listens for `start_fireplace` and `start_epic_sax` events to play a pre-defined movie.

**media_buttons**
Listens for the events `keyboard.volume_up`, `keyboard.volume_down` and `keyboard.media_play_pause` to simulate the pressing of the appropriate media button.
Depends on: PyUserInput
