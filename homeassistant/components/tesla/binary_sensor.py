"""Support for Tesla binary sensor."""
import logging

from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    async_add_entities(
        [
            TeslaBinarySensor(
                device,
                hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"],
                config_entry,
            )
            for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"][
                "binary_sensor"
            ]
        ],
        True,
    )


class TeslaBinarySensor(TeslaDevice, BinarySensorEntity):
    """Implement an Tesla binary sensor for parking and charger."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise of a Tesla binary sensor."""
        super().__init__(tesla_device, controller, config_entry)
        self._state = None
        self._sensor_type = None
        if tesla_device.sensor_type in DEVICE_CLASSES:
            self._sensor_type = tesla_device.sensor_type

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    async def async_update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        await super().async_update()
        self._state = self.tesla_device.get_value()
        self._attributes = self.tesla_device.attrs
