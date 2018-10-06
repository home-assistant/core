"""
Support for Rflink binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rflink/
"""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA)
from homeassistant.components.rflink import (
    CONF_ALIASES, CONF_DEVICES, DATA_ENTITY_LOOKUP, DOMAIN,
    EVENT_KEY_COMMAND, RflinkDevice, cv, vol)
from homeassistant.const import (
    CONF_FORCE_UPDATE, CONF_NAME, CONF_DEVICE_CLASS, CONF_PLATFORM, STATE_OFF,
    STATE_ON)
import homeassistant.helpers.event as evt

CONF_OFF_DELAY = 'off_delay'
DEFAULT_FORCE_UPDATE = False

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_DEVICE_CLASS):
                DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE):
                cv.boolean,
            vol.Optional(CONF_OFF_DELAY):
                vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Optional(CONF_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
        },
    }),
})


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device = RflinkBinarySensor(device_id, hass, **config)
        devices.append(device)

        # Register entity (and aliases) to listen to incoming rflink events
        hass.data[DATA_ENTITY_LOOKUP][
            EVENT_KEY_COMMAND][device_id].append(device)
        aliases = config.get(CONF_ALIASES)
        if aliases:
            for _id in aliases:
                hass.data[DATA_ENTITY_LOOKUP][
                    EVENT_KEY_COMMAND][_id].append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config, hass))


class RflinkBinarySensor(RflinkDevice):
    """Representation of an Rflink sensor."""

    def __init__(self, device_id, hass, device_class=None,
                 force_update=None, off_delay=None,
                 **kwargs):
        """Handle sensor specific args and super init."""
        self._device_class = device_class
        self._force_update = force_update
        self._off_delay = off_delay
        self._delay_listener = None
        super().__init__(device_id, hass, **kwargs)

    def _handle_event(self, event):
        """Domain specific event handler."""
        command = event['command']
        if command == 'on':
            self._state = True
        elif command == 'off':
            self._state = False

        if (self._state and self._off_delay is not None):
            def off_delay_listener(now):
                """Switch device off after a delay."""
                self._delay_listener = None
                self._state = False
                self.async_schedule_update_ha_state()
            if self._delay_listener is not None:
                self._delay_listener()
            self._delay_listener = evt.async_call_later(
                self.hass, self._off_delay, off_delay_listener)
        self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def force_update(self):
        """Force update."""
        return self._force_update
