#!/usr/bin/python2
""" Starts home assistant with all possible functionality. """

from ConfigParser import SafeConfigParser

from homeassistant import StateMachine, EventBus, start_home_assistant
from homeassistant import observers
from homeassistant import actors
from homeassistant.httpinterface import HTTPInterface

# Read config
config = SafeConfigParser()
config.read("home-assistant.conf")

# Init core
eventbus = EventBus()
statemachine = StateMachine(eventbus)

# Init observers
tomato = observers.TomatoDeviceScanner(config.get('tomato','host'),
                                       config.get('tomato','username'),
                                       config.get('tomato','password'),
                                       config.get('tomato','http_id'))

devicetracker = observers.DeviceTracker(eventbus, statemachine, tomato)

observers.track_sun(eventbus, statemachine,
                    config.get("common","latitude"),
                    config.get("common","longitude"))

# Init actors
actors.LightTrigger(eventbus, statemachine,
                    devicetracker, actors.HueLightControl())

actors.setup_chromecast(eventbus, config.get("chromecast", "host"))
actors.setup_file_downloader(eventbus, config.get("downloader", "download_dir"))
actors.setup_webbrowser(eventbus)

# Init HTTP interface
HTTPInterface(eventbus, statemachine, config.get("common","api_password"))

start_home_assistant(eventbus)
