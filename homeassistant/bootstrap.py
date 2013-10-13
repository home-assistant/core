"""
Provides methods to bootstrap a home assistant instance.
"""

import ConfigParser

import homeassistant as ha
import homeassistant.observers as observers
import homeassistant.actors as actors
import homeassistant.httpinterface as httpinterface

def from_config_file(config_path):
    """ Starts home assistant with all possible functionality
        based on a config file. """

    # Read config
    config = ConfigParser.SafeConfigParser()
    config.read(config_path)

    # Init core
    eventbus = ha.EventBus()
    statemachine = ha.StateMachine(eventbus)

    # Init observers
    # Device scanner
    if config.has_option('tomato', 'host') and \
        config.has_option('tomato', 'username') and \
        config.has_option('tomato', 'password') and \
        config.has_option('tomato', 'http_id'):

        device_scanner = observers.TomatoDeviceScanner(
                                            config.get('tomato','host'),
                                            config.get('tomato','username'),
                                            config.get('tomato','password'),
                                            config.get('tomato','http_id'))

    else:
        device_scanner = None


    # Device Tracker
    if device_scanner:
        device_tracker = observers.DeviceTracker(eventbus, statemachine,
                                                            device_scanner)
    else:
        device_tracker = None


    # Sun tracker
    if config.has_option("common", "latitude") and \
        config.has_option("common", "longitude"):

        observers.track_sun(eventbus, statemachine,
                            config.get("common","latitude"),
                            config.get("common","longitude"))

    # Init actors
    # Light control
    if config.has_section("hue"):
        if config.has_option("hue", "host"):
            hue_host = config.get("hue", "host")
        else:
            hue_host = None

        light_control = actors.HueLightControl(hue_host)


    # Light trigger
    if light_control:
        actors.LightTrigger(eventbus, statemachine,
                            device_tracker, light_control)


    if config.has_option("chromecast", "host"):
        actors.setup_chromecast(eventbus, config.get("chromecast", "host"))


    if config.has_option("downloader", "download_dir"):
        actors.setup_file_downloader(eventbus,
                                     config.get("downloader", "download_dir"))

    actors.setup_webbrowser(eventbus)
    actors.setup_media_buttons(eventbus)

    # Init HTTP interface
    if config.has_option("httpinterface", "api_password"):
        httpinterface.HTTPInterface(eventbus, statemachine,
                                    config.get("httpinterface","api_password"))


    ha.start_home_assistant(eventbus)
