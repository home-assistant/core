"""
Provides methods to bootstrap a home assistant instance.
"""

import ConfigParser
import logging

import homeassistant as ha
import homeassistant.observers as observers
import homeassistant.actors as actors
import homeassistant.httpinterface as httpinterface


# pylint: disable=too-many-branches
def from_config_file(config_path):
    """ Starts home assistant with all possible functionality
        based on a config file. """

    statusses = []

    # Read config
    config = ConfigParser.SafeConfigParser()
    config.read(config_path)

    # Init core
    bus = ha.Bus()
    statemachine = ha.StateMachine(bus)

    # Init observers
    # Device scanner
    if config.has_option('tomato', 'host') and \
       config.has_option('tomato', 'username') and \
       config.has_option('tomato', 'password') and \
       config.has_option('tomato', 'http_id'):

        device_scanner = observers.TomatoDeviceScanner(
            config.get('tomato', 'host'),
            config.get('tomato', 'username'),
            config.get('tomato', 'password'),
            config.get('tomato', 'http_id'))

        if device_scanner.success_init:
            statusses.append(("Device Scanner - Tomato", True))

        else:
            statusses.append(("Device Scanner - Tomato", False))

            device_scanner = None

    else:
        device_scanner = None

    # Device Tracker
    if device_scanner:
        device_tracker = observers.DeviceTracker(
            bus, statemachine, device_scanner)

        statusses.append(("Device Tracker", True))

    else:
        device_tracker = None

    # Sun tracker
    if config.has_option("common", "latitude") and \
       config.has_option("common", "longitude"):

        statusses.append(("Weather - Ephem",
                          observers.track_sun(
                              bus, statemachine,
                              config.get("common", "latitude"),
                              config.get("common", "longitude"))))

    if config.has_option("chromecast", "host"):
        statusses.append(("Chromecast",
                          observers.setup_chromecast(
                              bus, statemachine,
                              config.get("chromecast", "host"))))

    # --------------------------
    # Init actors
    # Light control
    if config.has_section("hue"):
        if config.has_option("hue", "host"):
            light_control = actors.HueLightControl(config.get("hue", "host"))
        else:
            light_control = actors.HueLightControl()

        statusses.append(("Light Control - Hue", light_control.success_init))

    else:
        light_control = None

    # Light trigger
    if light_control:
        observers.setup_light_control_services(bus, statemachine, light_control)

        actors.LightTrigger(bus, statemachine,
                            device_tracker, light_control)

        statusses.append(("Light Trigger", True))

    if config.has_option("downloader", "download_dir"):
        result = actors.setup_file_downloader(
            bus, config.get("downloader", "download_dir"))

        statusses.append(("Downloader", result))

    statusses.append(("Webbrowser", actors.setup_webbrowser(bus)))

    statusses.append(("Media Buttons", actors.setup_media_buttons(bus)))

    # Init HTTP interface
    if config.has_option("httpinterface", "api_password"):
        httpinterface.HTTPInterface(
            bus, statemachine,
            config.get("httpinterface", "api_password"))

        statusses.append(("HTTPInterface", True))

    logger = logging.getLogger(__name__)

    for component, success_init in statusses:
        status = "initialized" if success_init else "Failed to initialize"

        logger.info("{}: {}".format(component, status))

    ha.start_home_assistant(bus)
