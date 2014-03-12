"""
Provides methods to bootstrap a home assistant instance.
"""

import importlib
import ConfigParser
import logging

import homeassistant as ha
import homeassistant.components as components


# pylint: disable=too-many-branches,too-many-locals,too-many-statements
def from_config_file(config_path):
    """ Starts home assistant with all possible functionality
        based on a config file. """

    # Setup the logging for home assistant.
    logging.basicConfig(level=logging.INFO)

    # Log errors to a file
    err_handler = logging.FileHandler("home-assistant.log",
                                      mode='w', delay=True)
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)s: %(message)s',
                          datefmt='%H:%M %d-%m-%y'))
    logging.getLogger('').addHandler(err_handler)

    # Start the actual bootstrapping
    logger = logging.getLogger(__name__)

    statusses = []

    # Read config
    config = ConfigParser.SafeConfigParser()
    config.read(config_path)

    # Init core
    bus = ha.Bus()
    statemachine = ha.StateMachine(bus)

    has_opt = config.has_option
    get_opt = config.get
    has_section = config.has_section
    add_status = lambda name, result: statusses.append((name, result))
    load_module = lambda module: importlib.import_module(
        'homeassistant.components.'+module)

    def get_opt_safe(section, option, default=None):
        """ Failure proof option retriever. """
        try:
            return config.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

    # Device scanner
    dev_scan = None

    try:
        # For the error message if not all option fields exist
        opt_fields = "host, username, password"

        if has_section('device_tracker.tomato'):
            device_tracker = load_module('device_tracker')

            dev_scan_name = "Tomato"
            opt_fields += ", http_id"

            dev_scan = device_tracker.TomatoDeviceScanner(
                get_opt('device_tracker.tomato', 'host'),
                get_opt('device_tracker.tomato', 'username'),
                get_opt('device_tracker.tomato', 'password'),
                get_opt('device_tracker.tomato', 'http_id'))

        elif has_section('device_tracker.netgear'):
            device_tracker = load_module('device_tracker')

            dev_scan_name = "Netgear"

            dev_scan = device_tracker.NetgearDeviceScanner(
                get_opt('device_tracker.netgear', 'host'),
                get_opt('device_tracker.netgear', 'username'),
                get_opt('device_tracker.netgear', 'password'))

    except ConfigParser.NoOptionError:
        # If one of the options didn't exist
        logger.exception(("Error initializing {}DeviceScanner, "
                          "could not find one of the following config "
                          "options: {}".format(dev_scan_name, opt_fields)))

        add_status("Device Scanner - {}".format(dev_scan_name), False)

    if dev_scan:
        add_status("Device Scanner - {}".format(dev_scan_name),
                   dev_scan.success_init)

        if not dev_scan.success_init:
            dev_scan = None

    # Device Tracker
    if dev_scan:
        device_tracker.DeviceTracker(bus, statemachine, dev_scan)

        add_status("Device Tracker", True)

    # Sun tracker
    if has_opt("common", "latitude") and \
       has_opt("common", "longitude"):

        sun = load_module('sun')

        add_status("Weather - Ephem",
                   sun.setup(
                       bus, statemachine,
                       get_opt("common", "latitude"),
                       get_opt("common", "longitude")))
    else:
        sun = None

    # Chromecast
    if has_section("chromecast"):
        chromecast = load_module('chromecast')

        chromecast_started = chromecast.setup(bus, statemachine)

        add_status("Chromecast", chromecast_started)
    else:
        chromecast_started = False

    # Light control
    if has_section("light.hue"):
        light = load_module('light')

        light_control = light.HueLightControl(get_opt_safe("hue", "host"))

        add_status("Light - Hue", light_control.success_init)

        light.setup(bus, statemachine, light_control)
    else:
        light_control = None

    if has_opt("downloader", "download_dir"):
        downloader = load_module('downloader')

        add_status("Downloader", downloader.setup(
            bus, get_opt("downloader", "download_dir")))

    add_status("Core components", components.setup(bus))

    if has_section('browser'):
        add_status("Browser", load_module('browser').setup(bus))

    if has_section('keyboard'):
        add_status("Keyboard", load_module('keyboard').setup(bus))

    # Init HTTP interface
    if has_opt("httpinterface", "api_password"):
        httpinterface = load_module('httpinterface')

        httpinterface.HTTPInterface(
            bus, statemachine,
            get_opt("httpinterface", "api_password"))

        add_status("HTTPInterface", True)

    # Init groups
    if has_section("group"):
        group = load_module('group')

        for name, entity_ids in config.items("group"):
            add_status("Group - {}".format(name),
                       group.setup(bus, statemachine, name,
                                   entity_ids.split(",")))

    # Light trigger
    if light_control and sun:
        device_sun_light_trigger = load_module('device_sun_light_trigger')

        light_group = get_opt_safe("device_sun_light_trigger", "light_group")

        add_status("Device Sun Light Trigger",
                   device_sun_light_trigger.setup(bus, statemachine,
                                                  light_group))

    for component, success_init in statusses:
        status = "initialized" if success_init else "Failed to initialize"

        logger.info("{}: {}".format(component, status))

    ha.start_home_assistant(bus)
