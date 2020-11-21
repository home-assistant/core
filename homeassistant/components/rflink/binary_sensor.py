"""Support for Rflink binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.event as evt

from . import CONF_ALIASES, CONF_DEVICES, RflinkDevice

_LOGGER = logging.getLogger(__name__)

CONF_OFF_DELAY = "off_delay"
DEFAULT_FORCE_UPDATE = False
TYPE_STANDARD = "standard"
TYPE_INVERTED = "inverted"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_TYPE): vol.Any(TYPE_STANDARD, TYPE_INVERTED),
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


def entity_class_for_type(entity_type):
    """Translate entity type to entity class.

    Async friendly.
    """
    entity_device_mapping = {
        # default cover implementation
        TYPE_STANDARD: RflinkBinarySensor,
        # binary sensor with on/off commands inverted
        TYPE_INVERTED: InvertedRflinkBinarySensor,
    }

    return entity_device_mapping.get(entity_type, RflinkBinarySensor)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        # Remove type from config to not pass it as and argument
        # to entity instantiation
        entity_type = config.pop(CONF_TYPE, TYPE_STANDARD)
        entity_class = entity_class_for_type(entity_type)
        device = entity_class(device_id, **config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))


class RflinkBinarySensor(RflinkDevice, BinarySensorEntity):
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
        self._update_state(event)

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

    def _update_state(self, event):
        """Device specific state update."""
        command = event["command"]
        if command in ["on", "allon"]:
            self._state = True
        elif command in ["off", "alloff"]:
            self._state = False
        else:
            _LOGGER.warning("%s' command not recognized")

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


class InvertedRflinkBinarySensor(RflinkBinarySensor):
    """Representation of an 'inverted' Rflink binary sensor."""

    def _update_state(self, event):
        """Device specific state update."""
        command = event["command"]
        if command in ["off", "alloff"]:
            self._state = True
        elif command in ["on", "allon"]:
            self._state = False
        else:
            _LOGGER.warning("%s' command not recognized")
