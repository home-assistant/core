"""Support for Fritzbox binary sensors."""
import requests

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.const import CONF_DEVICES

from .const import CONF_CONNECTIONS, DOMAIN as FRITZBOX_DOMAIN, LOGGER


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fritzbox binary sensor from config_entry."""
    devices = []
    device_ids = hass.data[FRITZBOX_DOMAIN][CONF_DEVICES]
    fritz = hass.data[FRITZBOX_DOMAIN][CONF_CONNECTIONS][config_entry.entry_id]

    for device in fritz.get_devices():
        if device.has_alarm and device.ain not in device_ids:
            devices.append(FritzboxBinarySensor(device, fritz))
            device_ids.add(device.ain)

    async_add_entities(devices, True)


class FritzboxBinarySensor(BinarySensorDevice):
    """Representation of a binary Fritzbox device."""

    def __init__(self, device, fritz):
        """Initialize the Fritzbox binary sensor."""
        self._device = device
        self._fritz = fritz

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(FRITZBOX_DOMAIN, self._device.ain)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.productname,
            "sw_version": self._device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return f"{self._device.ain}-{DOMAIN}"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._device.name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return "window"

    @property
    def is_on(self):
        """Return true if sensor is on."""
        if not self._device.present:
            return False
        return self._device.alert_state

    def update(self):
        """Get latest data from the Fritzbox."""
        try:
            self._device.update()
        except requests.exceptions.HTTPError as ex:
            LOGGER.warning("Connection error: %s", ex)
            self._fritz.login()
