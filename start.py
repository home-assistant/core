from ConfigParser import SafeConfigParser

from homeassistant import StateMachine, EventBus, start_home_assistant

from homeassistant.observers import TomatoDeviceScanner, DeviceTracker, WeatherWatcher
from homeassistant.actors import HueLightControl, LightTrigger
from homeassistant.httpinterface import HTTPInterface
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

weatherwatcher = WeatherWatcher(eventbus, statemachine,
								config.get("common","latitude"),
								config.get("common","longitude"))

# Init actors
LightTrigger(eventbus, statemachine, weatherwatcher, devicetracker, HueLightControl())

# Init HTTP interface
HTTPInterface(eventbus, statemachine, config.get("common","api_password"))

start_home_assistant(eventbus)
