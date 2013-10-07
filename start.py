from ConfigParser import SafeConfigParser

from homeassistant import StateMachine, EventBus, start_home_assistant

from homeassistant.observers import TomatoDeviceScanner, DeviceTracker, track_sun
from homeassistant.actors import HueLightControl, LightTrigger, setup_file_downloader
from homeassistant.httpinterface import HTTPInterface

from lib.pychromecast import play_youtube_video

# Read config
config = SafeConfigParser()
config.read("home-assistant.conf")

# Init core
eventbus = EventBus()
statemachine = StateMachine(eventbus)

# Init observers
tomato = TomatoDeviceScanner(config.get('tomato','host'), config.get('tomato','username'),
                             config.get('tomato','password'), config.get('tomato','http_id'))

devicetracker = DeviceTracker(eventbus, statemachine, tomato)

track_sun(eventbus, statemachine, config.get("common","latitude"), config.get("common","longitude"))

# Init actors
LightTrigger(eventbus, statemachine, devicetracker, HueLightControl())

# If a chromecast is specified, add some chromecast specific event triggers
if config.has_option("chromecast", "host"):
	eventbus.listen("start_fireplace", lambda event: play_youtube_video(config.get("chromecast","host"), "eyU3bRy2x44"))
	eventbus.listen("start_epic_sax", lambda event: play_youtube_video(config.get("chromecast","host"), "kxopViU98Xo"))

setup_file_downloader(eventbus, "downloads")

# Init HTTP interface
HTTPInterface(eventbus, statemachine, config.get("common","api_password"))

start_home_assistant(eventbus)
