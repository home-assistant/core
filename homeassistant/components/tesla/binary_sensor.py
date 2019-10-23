"""Support for Tesla binary sensor."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tesla binary sensor."""
    devices = [
        TeslaBinarySensor(device, hass.data[TESLA_DOMAIN]["controller"], "connectivity")
        for device in hass.data[TESLA_DOMAIN]["devices"]["binary_sensor"]
    ]
    add_entities(devices, True)
    return True


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Tesla binary_sensors by config_entry."""
    return await hass.async_add_executor_job(
        setup_platform, hass, config_entry.data, async_add_devices, None
    )


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    for device in hass.data[TESLA_DOMAIN]["devices"]["binary_sensor"]:
        await device.async_remove()
    return True


class TeslaBinarySensor(TeslaDevice, BinarySensorDevice):
    """Implement an Tesla binary sensor for parking and charger."""

    def __init__(self, tesla_device, controller, sensor_type):
        """Initialise of a Tesla binary sensor."""
        super().__init__(tesla_device, controller)
        self._state = False
        self._sensor_type = sensor_type

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return self._sensor_type

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        self.tesla_device.update()
        self._state = self.tesla_device.get_value()
