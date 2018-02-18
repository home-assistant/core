"""
Support for MAX! shutter contacts.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.maxcul/
"""
import logging
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES, PLATFORM_SCHEMA
)
from homeassistant.const import (
    CONF_ID, CONF_DEVICES, CONF_DEVICE_CLASS
)
from homeassistant.components.maxcul import (
    DATA_MAXCUL, SIGNAL_SHUTTER_UPDATE
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['maxcul']

DEFAULT_DEVICE_CLASS = 'opening'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS):
    vol.In(DEVICE_CLASSES),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.Schema({
        cv.string: DEVICE_SCHEMA
    })
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the maxcul binary sensor platform."""
    devices = [
        MaxShutterContact(
            hass,
            device[CONF_ID],
            name,
            device[CONF_DEVICE_CLASS]
        )
        for name, device
        in config[CONF_DEVICES].items()
    ]
    add_devices(devices)


class MaxShutterContact(BinarySensorDevice):
    """Representation of a MAX! shutter contact."""

    def __init__(self, hass, device_id, name,
                 device_class=DEFAULT_DEVICE_CLASS):
        """Initialize new MaxShutterContact with given id, name and class."""
        from maxcul import (
            ATTR_DEVICE_ID,
            ATTR_STATE
        )
        self._name = name
        self._device_id = device_id
        self._device_class = device_class
        self._is_open = None
        self._maxcul_handle = hass.data[DATA_MAXCUL]

        self._maxcul_handle.add_paired_device(self._device_id)

        @callback
        def update(event):
            """Handle thermostat update events."""
            device_id = event.data.get(ATTR_DEVICE_ID)
            if device_id != self._device_id:
                return
            self._is_open = event.data.get(ATTR_STATE, None)

            self.async_schedule_update_ha_state()

        dispatcher_connect(hass, SIGNAL_SHUTTER_UPDATE, update)

        self._maxcul_handle.wakeup(self._device_id)

    @property
    def should_poll(self):
        """Return whether home assistant should poll state of device."""
        return False

    @property
    def name(self):
        """Return the name of the shutter contact."""
        return self._name

    @property
    def is_on(self):
        """Return true if shutter is open."""
        return self._is_open

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class
