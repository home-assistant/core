"""Support for AVM Fritz!Box smarthome temperature sensor only devices."""
import requests

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    DOMAIN as FRITZBOX_DOMAIN,
    LOGGER,
)


async def async_setup_platform(
    hass, config, add_entities, discovery_info=None
):  # pragma: no cover
    """Set up the Fritzbox smarthome sensor platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fritzbox smarthome sensor from config_entry."""
    LOGGER.debug("Initializing fritzbox temperature sensors")
    devices = []
    fritz_list = hass.data[FRITZBOX_DOMAIN]

    for fritz in fritz_list:
        device_list = fritz.get_devices()
        for device in device_list:
            if (
                device.has_temperature_sensor
                and not device.has_switch
                and not device.has_thermostat
            ):
                devices.append(FritzBoxTempSensor(device, fritz))

    async_add_entities(devices)


class FritzBoxTempSensor(Entity):
    """The entity class for Fritzbox temperature sensors."""

    def __init__(self, device, fritz):
        """Initialize the switch."""
        self._device = device
        self._fritz = fritz

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(FRITZBOX_DOMAIN, self.unique_id)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.productname,
            "sw_version": self._device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._device.ain

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Get latest data and states from the device."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            LOGGER.warning("Fritzhome connection error: %s", ex)
            self._fritz.login()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {
            ATTR_STATE_DEVICE_LOCKED: self._device.device_lock,
            ATTR_STATE_LOCKED: self._device.lock,
        }
        return attrs
