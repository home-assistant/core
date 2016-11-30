"""
Contains functionality to use a flic button as a binary sensor.
"""
import asyncio
import logging
from datetime import datetime

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.components.binary_sensor import BinarySensorDevice, PLATFORM_SCHEMA
from homeassistant.util.async import fire_coroutine_threadsafe, run_callback_threadsafe


REQUIREMENTS = ['https://github.com/soldag/pyflic/archive/0.4.zip#pyflic==0.4']

_LOGGER = logging.getLogger(__name__)


CONF_AUTO_SCAN = "auto_scan"
CONF_THRESHOLDS = "thresholds"
CONF_THRESHOLD_DOUBLE_CLICK = "double_click"
CONF_THRESHOLD_LONG_CLICK = "long_click"

EVENT_FLIC_SINGLE_CLICK = "flic_single_click"
EVENT_FLIC_LONG_CLICK = "flic_long_click"
EVENT_FLIC_DOUBLE_CLICK = "flic_double_click"


# Validation of the user's configuration
THRESHOLDS_SCHEMA = vol.Schema({
    vol.Optional(CONF_THRESHOLD_LONG_CLICK, default=500): float,
    vol.Optional(CONF_THRESHOLD_DOUBLE_CLICK, default=300): float
})
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=5551): cv.port,
    vol.Optional(CONF_AUTO_SCAN, default=True): cv.boolean,
    vol.Optional(CONF_THRESHOLDS): THRESHOLDS_SCHEMA
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the flic platform."""
    import pyflic

    # Get event loop
    loop = asyncio.get_event_loop()

    # Initialize main flic client responsible for connecting to buttons and retrieve events
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    try:
        main_client = pyflic.FlicClient(host, port)
    except ConnectionRefusedError:
        _LOGGER.error("Failed to connect to flic server.")
        return

    def new_button_callback(address):
        asyncio.ensure_future(setup_button(hass, config, async_add_entities, main_client, address), loop=loop)

    main_client.on_new_verified_button = new_button_callback
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda: main_client.close())
    loop.run_in_executor(None, main_client.handle_events)

    # Initialize scan flic client responsible for scanning for new buttons
    auto_scan = config.get(CONF_AUTO_SCAN)
    if auto_scan:
        scan_client = pyflic.FlicClient(host, port)
        start_scanning(hass, config, async_add_entities, scan_client)
        loop.run_in_executor(None, scan_client.handle_events)

    # Get addresses of already verified buttons
    addresses = yield from get_verified_addresses(main_client)
    if addresses:
        for address in addresses:
            yield from setup_button(hass, config, async_add_entities, main_client, address)


def start_scanning(hass, config, async_add_entities, client):
    """Start a new flic client for scanning for new buttons and connecting to them."""
    import pyflic

    _LOGGER.info("Start scan wizard")
    scan_wizard = pyflic.ScanWizard()

    def scan_callback(scan_wizard, result, address, name):
        if result == pyflic.ScanWizardResult.WizardSuccess:
            _LOGGER.info("Found new button " + name + " (" + address + ")")

            # Restart scan wizard
            start_scanning(hass, config, async_add_entities, client)
        else:
            _LOGGER.info("Failed to connect to button (" + address + "). Reason: " + result)

    scan_wizard.on_completed = scan_callback
    client.add_scan_wizard(scan_wizard)


@asyncio.coroutine
def setup_button(hass, config, async_add_entities, client, address):
    """Setup single button device"""
    double_click_threshold = config.get(CONF_THRESHOLDS)[CONF_THRESHOLD_DOUBLE_CLICK]
    long_click_threshold = config.get(CONF_THRESHOLDS)[CONF_THRESHOLD_LONG_CLICK]

    button = FlicButton(hass, client, address, double_click_threshold, long_click_threshold)
    _LOGGER.info("Connected to button (" + address + ")")

    yield from async_add_entities([button])


def get_verified_addresses(client):
    """Retrieve addresses of verified buttons"""
    future = asyncio.Future()
    loop = asyncio.get_event_loop()

    def callback(items):
        addresses = items["bd_addr_of_verified_buttons"]
        run_callback_threadsafe(loop, future.set_result, addresses)
    client.get_info(callback)

    return future


class FlicButton(BinarySensorDevice):
    """Representation of a flic button."""

    def __init__(self, hass, client, address, double_click_threshold, long_click_threshold):
        """Initialize the flic button."""
        import pyflic

        self._hass = hass
        self._address = address
        self._double_click_threshold = double_click_threshold
        self._long_click_threshold = long_click_threshold
        self._is_down = False
        self._last_click = self._last_down = self._last_up = datetime.min

        # Initialize connection channel
        self._channel = pyflic.ButtonConnectionChannel(self._address)
        self._channel.on_button_up_or_down = self._button_up_down
        client.add_connection_channel(self._channel)


    @property
    def name(self):
        """Return the name of the device."""
        return self.address.replace(":", "")

    @property
    def address(self):
        """Return the bluetooth address of the device."""
        return self._address

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._is_down

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        attr = super(FlicButton, self).state_attributes
        attr["address"] = self.address

        return attr

    def _button_up_down(self, channel, click_type, was_queued, time_diff):
        """Called when the button is pressed or released"""
        import pyflic

        if not was_queued:
            # Set state
            self._is_down = click_type == pyflic.ClickType.ButtonDown
            self.update_ha_state()

            # Fire events
            now = datetime.now()
            if self._is_down:
                self._last_down = now
            else:
                self._last_up = now
                diff = now - self._last_down
                if diff.total_seconds() >= self._long_click_threshold:
                    self._hass.bus.fire(EVENT_FLIC_LONG_CLICK, self.address)
                else:
                    diff = now - self._last_click
                    if diff.total_seconds() <= self._double_click_threshold:
                        self._last_click = datetime.min
                        self._hass.bus.fire(EVENT_FLIC_DOUBLE_CLICK, self.address)
                    else:
                        self._last_click = now

                        @asyncio.coroutine
                        def defer_trigger():
                            yield from asyncio.sleep(self._double_click_threshold)
                            if self._last_click == now:
                                self._last_click = datetime.now()
                                self._hass.bus.fire(EVENT_FLIC_SINGLE_CLICK, self.address)
                        fire_coroutine_threadsafe(defer_trigger(), self._hass.loop)
