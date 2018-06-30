"""
Support for Velbus covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.velbus/
"""
import logging
import time

import voluptuous as vol

from homeassistant.components.cover import (
    CoverDevice, PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE,
    SUPPORT_STOP)
from homeassistant.components.velbus import DOMAIN
from homeassistant.const import (CONF_COVERS, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

COVER_SCHEMA = vol.Schema({
    vol.Required('module'): cv.positive_int,
    vol.Required('open_channel'): cv.positive_int,
    vol.Required('close_channel'): cv.positive_int,
    vol.Required(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})

DEPENDENCIES = ['velbus']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up cover controlled by Velbus."""
    devices = config.get(CONF_COVERS, {})
    covers = []

    velbus = hass.data[DOMAIN]
    for device_name, device_config in devices.items():
        covers.append(
            VelbusCover(
                velbus,
                device_config.get(CONF_NAME, device_name),
                device_config.get('module'),
                device_config.get('open_channel'),
                device_config.get('close_channel')
            )
        )

    if not covers:
        _LOGGER.error("No covers added")
        return False

    add_devices(covers)


class VelbusCover(CoverDevice):
    """Representation a Velbus cover."""

    def __init__(self, velbus, name, module, open_channel, close_channel):
        """Initialize the cover."""
        self._velbus = velbus
        self._name = name
        self._close_channel_state = None
        self._open_channel_state = None
        self._module = module
        self._open_channel = open_channel
        self._close_channel = close_channel

    async def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        def _init_velbus():
            """Initialize Velbus on startup."""
            self._velbus.subscribe(self._on_message)
            self.get_status()

        await self.hass.async_add_job(_init_velbus)

    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.RelayStatusMessage):
            if message.address == self._module:
                if message.channel == self._close_channel:
                    self._close_channel_state = message.is_on()
                    self.schedule_update_ha_state()
                if message.channel == self._open_channel:
                    self._open_channel_state = message.is_on()
                    self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._close_channel_state

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown.
        """
        return None

    def _relay_off(self, channel):
        import velbus
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self._velbus.send(message)

    def _relay_on(self, channel):
        import velbus
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self._velbus.send(message)

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._relay_off(self._close_channel)
        time.sleep(0.3)
        self._relay_on(self._open_channel)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._relay_off(self._open_channel)
        time.sleep(0.3)
        self._relay_on(self._close_channel)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._relay_off(self._open_channel)
        time.sleep(0.3)
        self._relay_off(self._close_channel)

    def get_status(self):
        """Retrieve current status."""
        import velbus
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = [self._open_channel, self._close_channel]
        self._velbus.send(message)
