"""Contains functionality to use flic buttons as a binary sensor."""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_DISCOVERY, EVENT_HOMEASSISTANT_STOP)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.util.async import run_callback_threadsafe


REQUIREMENTS = ['https://github.com/soldag/pyflic/archive/0.4.zip#pyflic==0.4']

_LOGGER = logging.getLogger(__name__)


EVENT_NAME = "flic_click"
EVENT_DATA_NAME = "button_name"
EVENT_DATA_ADDRESS = "button_address"
EVENT_DATA_TYPE = "click_type"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default='localhost'): cv.string,
    vol.Optional(CONF_PORT, default=5551): cv.port,
    vol.Optional(CONF_DISCOVERY, default=True): cv.boolean
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Setup the flic platform."""
    import pyflic

    # Initialize flic client responsible for
    # connecting to buttons and retrieving events
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    discovery = config.get(CONF_DISCOVERY)

    try:
        client = pyflic.FlicClient(host, port)
    except ConnectionRefusedError:
        _LOGGER.error("Failed to connect to flic server.")
        return

    def new_button_callback(address):
        """Setup newly verified button as device in home assistant."""
        hass.add_job(async_setup_button(hass, config, async_add_entities,
                                        client, address))

    client.on_new_verified_button = new_button_callback
    if discovery:
        start_scanning(hass, config, async_add_entities, client)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                               lambda event: client.close())
    hass.loop.run_in_executor(None, client.handle_events)

    # Get addresses of already verified buttons
    addresses = yield from async_get_verified_addresses(client)
    if addresses:
        for address in addresses:
            yield from async_setup_button(hass, config, async_add_entities,
                                          client, address)


def start_scanning(hass, config, async_add_entities, client):
    """Start a new flic client for scanning & connceting to new buttons."""
    import pyflic

    scan_wizard = pyflic.ScanWizard()

    def scan_completed_callback(scan_wizard, result, address, name):
        """Restart scan wizard to constantly check for new buttons."""
        if result == pyflic.ScanWizardResult.WizardSuccess:
            _LOGGER.info("Found new button (%s)", address)
        elif result != pyflic.ScanWizardResult.WizardFailedTimeout:
            _LOGGER.warning("Failed to connect to button (%s). Reason: %s",
                            address, result)

        # Restart scan wizard
        start_scanning(hass, config, async_add_entities, client)

    scan_wizard.on_completed = scan_completed_callback
    client.add_scan_wizard(scan_wizard)


@asyncio.coroutine
def async_setup_button(hass, config, async_add_entities, client, address):
    """Setup single button device."""
    button = FlicButton(hass, client, address)
    _LOGGER.info("Connected to button (%s)", address)

    yield from async_add_entities([button])


@asyncio.coroutine
def async_get_verified_addresses(client):
    """Retrieve addresses of verified buttons."""
    future = asyncio.Future()
    loop = asyncio.get_event_loop()

    def get_info_callback(items):
        """Set the addressed of connected buttons as result of the future."""
        addresses = items["bd_addr_of_verified_buttons"]
        run_callback_threadsafe(loop, future.set_result, addresses)
    client.get_info(get_info_callback)

    return future


class FlicButton(BinarySensorDevice):
    """Representation of a flic button."""

    def __init__(self, hass, client, address):
        """Initialize the flic button."""
        import pyflic

        self._hass = hass
        self._address = address
        self._is_down = False
        self._click_types = {
            pyflic.ClickType.ButtonSingleClick: "single",
            pyflic.ClickType.ButtonDoubleClick: "double",
            pyflic.ClickType.ButtonHold: "hold",
        }

        # Initialize connection channel
        self._channel = pyflic.ButtonConnectionChannel(self._address)
        self._channel.on_button_up_or_down = self._on_up_down
        self._channel.on_button_single_or_double_click_or_hold = self._on_click
        client.add_connection_channel(self._channel)

    @property
    def name(self):
        """Return the name of the device."""
        return "flic_%s" % self.address.replace(":", "")

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

    def _on_up_down(self, channel, click_type, was_queued, time_diff):
        """Update device state, if event was not queued."""
        import pyflic

        if was_queued:
            return

        self._is_down = click_type == pyflic.ClickType.ButtonDown
        self.schedule_update_ha_state()

    def _on_click(self, channel, click_type, was_queued, time_diff):
        """Fire click event, if event was not queued."""
        if was_queued:
            return

        self._hass.bus.fire(EVENT_NAME, {
            EVENT_DATA_NAME: self.name,
            EVENT_DATA_ADDRESS: self.address,
            EVENT_DATA_TYPE: self._click_types[click_type]
        })

    def _connection_status_changed(self, channel,
                                   connection_status, disconnect_reason):
        """Remove device, if button disconnects."""
        import pyflic

        if connection_status == pyflic.ConnectionStatus.Disconnected:
            _LOGGER.info("Button (%s) disconnected. Reason: %s",
                         self.address, disconnect_reason)
            self.remove()
