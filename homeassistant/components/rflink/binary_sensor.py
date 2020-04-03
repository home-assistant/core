"""Support for Rflink binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDevice,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_FORCE_UPDATE, CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.event as evt

from . import CONF_ALIASES, CONF_DEVICES, RflinkDevice

CONF_OFF_DELAY = "off_delay"
DEFAULT_FORCE_UPDATE = False

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                    vol.Optional(
                        CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
                    ): cv.boolean,
                    vol.Optional(CONF_OFF_DELAY): cv.positive_int,
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            )
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device = RflinkBinarySensor(device_id, **config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))


class RflinkBinarySensor(RflinkDevice, BinarySensorDevice):
    """Representation of an Rflink binary sensor."""

    def __init__(
        self, device_id, device_class=None, force_update=False, off_delay=None, **kwargs
    ):
        """Handle sensor specific args and super init."""
        self._state = None
        self._device_class = device_class
        self._force_update = force_update
        self._off_delay = off_delay
        self._delay_listener = None
        super().__init__(device_id, **kwargs)

    def _handle_event(self, event):
        """Domain specific event handler."""
        command = event["command"]
        if command == "on":
            self._state = True
        elif command == "off":
            self._state = False

        if self._state and self._off_delay is not None:

            def off_delay_listener(now):
                """Switch device off after a delay."""
                self._delay_listener = None
                self._state = False
                self.async_write_ha_state()

            if self._delay_listener is not None:
                self._delay_listener()
            self._delay_listener = evt.async_call_later(
                self.hass, self._off_delay, off_delay_listener
            )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update
