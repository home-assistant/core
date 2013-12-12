"""
Provides methods to bootstrap a home assistant instance.
"""

import ConfigParser
import logging

import homeassistant as ha
from homeassistant.components import (general, chromecast,
                                      device_sun_light_trigger, device,
                                      downloader, keyboard, light, sun,
                                      browser, httpinterface)


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

    # Device scanner
    if config.has_option('tomato', 'host') and \
       config.has_option('tomato', 'username') and \
       config.has_option('tomato', 'password') and \
       config.has_option('tomato', 'http_id'):

        device_scanner = device.TomatoDeviceScanner(
            config.get('tomato', 'host'),
            config.get('tomato', 'username'),
            config.get('tomato', 'password'),
            config.get('tomato', 'http_id'))

        statusses.append(("Device Scanner - Tomato",
                          device_scanner.success_init))

    elif config.has_option('netgear', 'host') and \
         config.has_option('netgear', 'username') and \
         config.has_option('netgear', 'password'):

        device_scanner = device.NetgearDeviceScanner(
            config.get('netgear', 'host'),
            config.get('netgear', 'username'),
            config.get('netgear', 'password'))

        statusses.append(("Device Scanner - Netgear",
                          device_scanner.success_init))

    else:
        device_scanner = None

    if device_scanner and not device_scanner.success_init:
        device_scanner = None

    # Device Tracker
    if device_scanner:
        device.DeviceTracker(bus, statemachine, device_scanner)

        statusses.append(("Device Tracker", True))

    # Sun tracker
    if config.has_option("common", "latitude") and \
       config.has_option("common", "longitude"):

        statusses.append(("Weather - Ephem",
                          sun.setup(
                              bus, statemachine,
                              config.get("common", "latitude"),
                              config.get("common", "longitude"))))

    # Chromecast
    if config.has_option("chromecast", "host"):
        chromecast_started = chromecast.setup(bus, statemachine,
                                              config.get("chromecast", "host"))

        statusses.append(("Chromecast", chromecast_started))
    else:
        chromecast_started = False

    # Light control
    if config.has_section("hue"):
        if config.has_option("hue", "host"):
            light_control = light.HueLightControl(config.get("hue", "host"))
        else:
            light_control = light.HueLightControl()

        statusses.append(("Light Control - Hue", light_control.success_init))

    else:
        light_control = None

    # Light trigger
    if light_control:
        light.setup(bus, statemachine, light_control)

        statusses.append(("Light Trigger", device_sun_light_trigger.setup(
                          bus, statemachine)))

    if config.has_option("downloader", "download_dir"):
        statusses.append(("Downloader", downloader.setup(
            bus, config.get("downloader", "download_dir"))))

    # Currently only works with Chromecast or Light_Control
    if chromecast_started or light_control:
        statusses.append(("General", general.setup(bus, statemachine)))

    statusses.append(("Browser", browser.setup(bus)))

    statusses.append(("Media Buttons", keyboard.setup(bus)))

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
