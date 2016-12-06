"""
Support for Flic buttons.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/flic/
"""
import logging
import threading

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_DISCOVERY,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5551
DEFAULT_DISCOVERY = True
DOMAIN = 'flic'
COMPONENT = 'binary_sensor'
ATTR_BD_ADDR = 'bd_addr'

CLIENT = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Use config values to set up the Flic client thread."""
    global CLIENT

    try:
        import fliclib
    except ImportError:
        _LOGGER.error("You are missing required dependency fliclib-linux-hci "
                      "python client-lib. Please follow instructions at: "
                      "https://home-assistant.io/components/flic/")
        return False

    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)

    configurator = get_component('configurator')
    configurator_request = None

    def button_added(bd_addr):
        """Called when a new button is registered with the flicd daemon."""
        nonlocal configurator_request

        if configurator_request:
            configurator.request_done(configurator_request)
            configurator_request = None

        discovery.load_platform(hass, COMPONENT, DOMAIN, {
            ATTR_BD_ADDR: bd_addr,
        }, config)

    def got_info(items):
        """Called during component setup to get state of flicd daemon."""
        for bd_addr in items["bd_addr_of_verified_buttons"]:
            button_added(bd_addr)

    # Create the FlicClient and register event handlers
    CLIENT = fliclib.FlicClient(host, port)
    CLIENT.on_new_verified_button = button_added

    # Request the current state of flicd
    CLIENT.get_info(got_info)

    if conf.get(CONF_DISCOVERY):
        wizard = fliclib.ScanWizard()

        def configurator_callback(data):
            """Configurator submit button pressed."""
            nonlocal configurator_request

            CLIENT.remove_scan_wizard(wizard)
            if configurator_request:
                configurator.request_done(configurator_request)
                configurator_request = None

        def on_found_private_button(wizard):
            """Found a button already paired to a different app."""
            nonlocal configurator_request

            if configurator_request is None:
                configurator_request = configurator.request_config(
                    hass, "Flic", configurator_callback, description=(
                        "An private Flic button was detected. Press and "
                        "hold the Flic button for at least 6 seconds to "
                        "pair with Home Assistant."),
                    entity_picture="/static/images/logo_flic.png",
                    submit_caption="Stop Scanning")

        wizard.on_found_private_button = on_found_private_button
        CLIENT.add_scan_wizard(wizard)

    flic_thread = FlicThread()

    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_START, lambda _: flic_thread.start())
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP, lambda _: CLIENT.close())

    return True


class FlicThread(threading.Thread):
    """This thread interfaces with flicd to read button events."""

    def __init__(self):
        """Construct a Flic interface object."""
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        """Main loop of the Flic interface thread."""
        _LOGGER.debug("Flic interface thread started")
        # Run the flic event loop
        CLIENT.handle_events()
        _LOGGER.debug("Flic interface thread stopped")
