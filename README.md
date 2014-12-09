# Home Assistant [![Build Status](https://travis-ci.org/balloob/home-assistant.svg?branch=master)](https://travis-ci.org/balloob/home-assistant) [![Coverage Status](https://img.shields.io/coveralls/balloob/home-assistant.svg)](https://coveralls.io/r/balloob/home-assistant?branch=master)

Home Assistant is a home automation platform running on Python 3. The goal of Home Assistant is to be able to track and control all devices at home and offer a platform for automating control.

It offers the following functionality through built-in components:

 * Track if devices are home by monitoring connected devices to a wireless router (supporting [OpenWrt](https://openwrt.org/), [Tomato](http://www.polarcloud.com/tomato), [Netgear](http://netgear.com))
 * Track and control [Philips Hue](http://meethue.com) lights
 * Track and control [WeMo switches](http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/)
 * Track and control [Google Chromecasts](http://www.google.com/intl/en/chrome/devices/chromecast)
 * Track running services by monitoring `ps` output
 * Track and control [Tellstick devices and sensors](http://www.telldus.se/products/tellstick)
 * Turn on the lights when people get home after sun set
 * Turn on lights slowly during sun set to compensate for light loss
 * Turn off all lights and devices when everybody leaves the house
 * Offers web interface to monitor and control Home Assistant
 * Offers a [REST API](#API) for easy integration with other projects ([see related projects for Android and Ruby support](#related_projects))
 * [Ability to have multiple instances of Home Assistant work together](#connected_instances)

Home Assistant also includes functionality for controlling HTPCs:

 * Simulate key presses for Play/Pause, Next track, Prev track, Volume up, Volume Down
 * Download files
 * Open URLs in the default browser

![screenshot-states](https://raw.github.com/balloob/home-assistant/master/docs/screenshots.png)

The system is built modular so support for other devices or actions can be implemented easily. See also the [section on architecture](#architecture) and the [section on customizing](#customizing).

If you run into issues while using Home Assistant or during development of a component, reach out to the [Home Assistant developer community](https://groups.google.com/forum/#!forum/home-assistant-dev).

## Installation instructions / Quick-start guide

Running Home Assistant requires that python3 and the package requests are installed.

Run the following code to get up and running with the minimum setup:

```python
git clone --recursive https://github.com/balloob/home-assistant.git
cd home-assistant
pip3 install -r requirements.txt

python3 -m homeassistant
```

This will start the Home Assistant server and create an initial configuration file in `config/home-assistant.conf` that is setup for demo mode. It will launch its web interface on [http://127.0.0.1:8123](http://127.0.0.1:8123). The default password is 'password'.

If you're using Docker, you can use

```bash
docker run -d --name="home-assistant" -v /path/to/homeassistant/config:/config -v /etc/localtime:/etc/localtime:ro -p 8123:8123 balloob/home-assistant
```

After you got the demo mode running it is time to enable some real components and get started. An example configuration file has been provided in [/config/home-assistant.conf.example](https://github.com/balloob/home-assistant/blob/master/config/home-assistant.conf.example).

*Note:* you can append `?api_password=YOUR_PASSWORD` to the url of the web interface to log in automatically.

*Note:* for the light and switch component, you can specify multiple types by using sequential sections: [switch], [switch 2], [switch 3] etc

### Philips Hue
To get Philips Hue working you will have to connect Home Assistant to the Hue bridge.

Run the following command from your config dir and follow the instructions:

```bash
python3 -m phue --host HUE_BRIDGE_IP_ADDRESS --config-file-path phue.conf
```

After that add the following lines to your `home-assistant.conf`:

```
[light]
platform=hue
```

### Wireless router

Your wireless router is used to track which devices are connected. Three different types of wireless routers are currently supported: tomato, netgear and luci (OpenWRT). To get started add the following lines to your `home-assistant.conf` (example for Netgear):

```
[device_tracker]
platform=netgear
host=192.168.1.1
username=admin
password=MY_PASSWORD
```

*Note on tomato:* Tomato requires an extra config variable called `http_id`. The value can be obtained by logging in to the Tomato admin interface and search for `http_id` in the page source code.

*Note on luci:* before the Luci scanner can be used you have to install the luci RPC package on OpenWRT: `opkg install luci-mod-rpc`.

Once tracking the `device_tracker` component will maintain a file in your config dir called `known_devices.csv`. Edit this file to adjust which devices have to be tracked.

<a name='customizing'></a>
## Further customizing Home Assistant

Home Assistant can be extended by components. Components can listen for- or trigger events and offer services. Components are written in Python and can do all the goodness that Python has to offer.

Home Assistant offers [built-in components](#components) but it is easy to built your own. An example component can be found in [`/config/custom_components/example.py`](https://github.com/balloob/home-assistant/blob/master/config/custom_components/example.py).

*Note:* Home Assistant will use the directory that contains your config file as the directory that holds your customizations. By default this is the `./config` folder but this can be pointed anywhere on the filesystem by using the `--config /YOUR/CONFIG/PATH/` argument.

A component will be loaded on start if a section (ie. `[light]`) for it exists in the config file or a module that depends on the component is loaded. When loading a component Home Assistant will check the following paths:

 * &lt;config file directory>/custom_components/&lt;component name>.py
 * homeassistant/components/&lt;component name>.py (built-in components)

Once loaded, a component will only be setup if all dependencies can be loaded and are able to setup. Keep an eye on the logs to see if loading and setup of your component went well.

*Warning:* You can override a built-in component by offering a component with the same name in your custom_components folder. This is not recommended and may lead to unexpected behavior!

After a component is loaded the bootstrapper will call its setup method `setup(hass, config)`:

| Parameter | Description |
| --------- | ----------- |
| hass | The Home Assistant object. Call its methods to track time, register services or listen for events. [Overview of available methods.](https://github.com/balloob/home-assistant/blob/master/homeassistant/__init__.py#L54) |
| config | A dict containing the configuration. The keys of the config-dict are component names and the value is another dict with configuration attributes. |

**Tips on using the Home Assistant object parameter**<br>
The Home Assistant object contains three objects to help you interact with the system.

| Object | Description |
| ------ | ----------- |
| hass.states | This is the StateMachine. The StateMachine allows you to see which states are available and set/test states for specified entities. [See API](https://github.com/balloob/home-assistant/blob/master/homeassistant/__init__.py#L460). |
| hass.events | This is the EventBus. The EventBus allows you to listen and trigger events. [See API](https://github.com/balloob/home-assistant/blob/master/homeassistant/__init__.py#L319). |
| hass.services | This is the ServiceRegistry. The ServiceRegistry allows you to register services. [See API](https://github.com/balloob/home-assistant/blob/master/homeassistant/__init__.py#L541). |

**Example on using the configuration parameter**<br>
If your configuration file containes the following lines:

```
[example]
host=paulusschoutsen.nl
```

Then in the setup-method of your component you will be able to refer to `config[example][host]` to get the value `paulusschoutsen.nl`.

If you want to get your component included with the Home Assistant distribution, please take a look at the [contributing page](https://github.com/balloob/home-assistant/blob/master/CONTRIBUTING.md).

<a name="architecture"></a>
## Architecture

The core of Home Assistant exists of three parts; an Event Bus for firing events, a State Machine that keeps track of the state of things and a Service Registry to manage services.

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

<a name='components'></a>
### Components

**sun**
Tracks the state of the sun and when the next sun rising and setting will occur.
Depends on: config variables common/latitude and common/longitude
Action: maintains state of `weather.sun` including attributes `next_rising` and `next_setting`

**device_tracker**
Keeps track of which devices are currently home.
Action: sets the state per device and maintains a combined state called `all_devices`. Keeps track of known devices in the file `config/known_devices.csv`.

**light**
Keeps track which lights are turned on and can control the lights. It has [4 built-in light profiles](https://github.com/balloob/home-assistant/blob/master/homeassistant/components/light/light_profiles.csv) which you're able to extend by putting a light_profiles.csv file in your config dir.

Registers services `light/turn_on` and `light/turn_off` to turn a or all lights on or off.

Optional service data:
  - `entity_id` - only act on specific light. Else targets all.
  - `transition_seconds` - seconds to take to swithc to new state.
  - `profile` - which light profile to use.
  - `xy_color` - two comma seperated floats that represent the color in XY
  - `rgb_color` - three comma seperated integers that represent the color in RGB
  - `brightness` - integer between 0 and 255 for how bright the color should be

**switch**
Keeps track which switches are in the network, their state and allows you to control them.

Registers services `switch/turn_on` and `switch/turn_off` to turn a or all switches on or off.

Optional service data:
 - `entity_id` - only act on specific switch. Else targets all.

**device_sun_light_trigger**
Turns lights on or off using a light control component based on state of the sun and devices that are home.
Depends on: light control, track_sun, device_tracker
Action:

 * Turns lights off when all devices leave home.
 * Turns lights on when a device is home while sun is setting.
 * Turns lights on when a device gets home after sun set.

**chromecast**
Registers 7 services to control playback on a Chromecast: `turn_off`, `volume_up`, `volume_down`, `media_play_pause`, `media_play`, `media_pause`, `media_next_track`.

Registers three services to start playing YouTube video's on the ChromeCast.

Service `chromecast/play_youtube_video` starts playing the specified video on the YouTube app on the ChromeCast. Specify video using `video` in service_data.

Service `chromecast/start_fireplace` will start a YouTube movie simulating a fireplace and the `chromecast/start_epic_sax` service will start playing Epic Sax Guy 10h version.

**keyboard**
Registers services that will simulate key presses on the keyboard. It currently offers the following Buttons as a Service (BaaS): `keyboard/volume_up`, `keyboard/volume_down` and `keyboard/media_play_pause`
This actor depends on: PyUserInput

**downloader**
Registers service `downloader/download_file` that will download files. File to download is specified in the `url` field in the service data.

**browser**
Registers service `browser/browse_url` that opens `url` as specified in event_data in the system default browser.

**tellstick_sensor**
Shows the values of that sensors that is connected to your Tellstick.

**simple_alarm**
Will provide simple alarm functionality. Will flash a light shortly if a known device comes home. Will flash the lights red if the lights turn on while no one is home.

Depends on device_tracker, light.

Config options:
known_light: entity id of the light/light group to target to flash when a known device comes home
unknown_light: entity if of the light/light group to target when a light is turned on while no one is at home.

<a name='API'></a>
## Rest API

Home Assistent runs a webserver accessible on port 8123.

  * At http://127.0.0.1:8123/ it will provide an interface allowing you to control Home Assistant.
  * At http://localhost:8123/api/ it provides a password protected API.

In the package `homeassistant.remote` a Python API on top of the HTTP API can be found.

The API accepts and returns only JSON encoded objects. All API calls have to be accompanied by the header "X-HA-Access" with as value the api password (as specified in `home-assistant.conf`).

Successful calls will return status code 200 or 201. Other status codes that can return are:
 - 400 (Bad Request)
 - 401 (Unauthorized)
 - 404 (Not Found)
 - 405 (Method not allowed)

The api supports the following actions:

**/api - GET**<br>
Returns message if API is up and running.

```json
{
  "message": "API running."
}
```

**/api/events - GET**<br>
Returns an array of event objects. Each event object contain event name and listener count.

```json
[
    {
      "event": "state_changed",
      "listener_count": 5
    },
    {
      "event": "time_changed",
      "listener_count": 2
    }
]
```

**/api/services - GET**<br>
Returns an array of service objects. Each object contains the domain and which services it contains.

```json
[
    {
      "domain": "browser",
      "services": [
        "browse_url"
      ]
    },
    {
      "domain": "keyboard",
      "services": [
        "volume_up",
        "volume_down"
      ]
    }
]
```

**/api/states - GET**<br>
Returns an array of state objects. Each state has the following attributes: entity_id, state, last_changed and attributes.

```json
[
    {
        "attributes": {
            "next_rising": "07:04:15 29-10-2013",
            "next_setting": "18:00:31 29-10-2013"
        },
        "entity_id": "sun.sun",
        "last_changed": "23:24:33 28-10-2013",
        "state": "below_horizon"
    },
    {
        "attributes": {},
        "entity_id": "process.Dropbox",
        "last_changed": "23:24:33 28-10-2013",
        "state": "on"
    }
]
```

**/api/states/&lt;entity_id>** - GET<br>
Returns a state object for specified entity_id. Returns 404 if not found.

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
Updates or creates the current state of an entity.

Return code is 200 if the entity existed, 201 if the state of a new entity was set. A location header will be returned with the url of the new resource. The response body will contain a JSON encoded State object.<br>
<br>
parameter: state - string<br>
optional parameter: attributes - JSON object

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
optional body: JSON encoded object that represents event_data

```json
{
    "message": "Event download_file fired."
}
```

**/api/services/&lt;domain>/&lt;service>** - POST<br>
Calls a service within a specific domain.<br>
optional body: JSON encoded object that represents service_data

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

<a name='connected_instances'></a>
## Connect multiple instances of Home Assistant

Home Assistant supports running multiple synchronzied instances using a master-slave model. Slaves forward all local events fired and states set to the master instance which will then replicate it to each slave.

Because each slave maintains its own ServiceRegistry it is possible to have multiple slaves respond to one service call.

![home assistant master-slave architecture](https://raw.github.com/balloob/home-assistant/master/docs/architecture-remote.png)

A slave instance can be started with the following code and has the same support for components as a master-instance.

```python
import homeassistant.remote as remote
import homeassistant.components.http as http

remote_api = remote.API("remote_host_or_ip", "remote_api_password")

hass = remote.HomeAssistant(remote_api)

http.setup(hass, "my_local_api_password")

hass.start()
hass.block_till_stopped()
```

<a name="related_projects"></a>
## Related projects

[Home Assistant API client in Ruby](https://github.com/balloob/home-assistant-ruby)<br>
[Home Assistant API client for Tasker for Android](https://github.com/balloob/home-assistant-android-tasker)
