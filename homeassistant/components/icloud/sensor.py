"""Support for iCloud sensors."""
import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import HomeAssistantType

from . import IcloudDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up iCloud devices sensors based on a config entry."""
    username = entry.data[CONF_USERNAME]
    icloud = hass.data[DOMAIN][username]

    devices = []
    for device_name, icloud_device in icloud.devices.items():
        if icloud_device.battery_level is not None:
            _LOGGER.debug("Adding sensors from iCloud device=%s", device_name)
            devices.append(
                IcloudDeviceBatterySensor(hass, icloud.username, icloud_device)
            )

    async_add_entities(devices, True)


class IcloudDeviceBatterySensor(Entity):
    """Representation of a iCloud device battery sensor."""

    def __init__(self, hass: HomeAssistantType, username: str, device: IcloudDevice):
        """Initialize the battery sensor."""
        self._hass = hass
        self._username = username
        self._device = device

    def update(self):
        """Fetch new state data for the sensor."""
        self._device = self._hass.data[DOMAIN][self._username].devices[
            self._device.unique_id
        ]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device.unique_id

    @property
    def name(self) -> str:
        """Sensor name."""
        return self._device.name + " battery state"

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self) -> int:
        """Battery state percentage."""
        return self._device.battery_level

    @property
    def unit_of_measurement(self) -> str:
        """Battery state measured in percentage."""
        return "%"

    @property
    def icon(self) -> str:
        """Battery state icon handling."""
        return icon_for_battery_level(
            battery_level=self._device.battery_level,
            charging=self._device.battery_status == "Charging",
        )

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return default attributes for the iCloud device entity."""
        return self._device.state_attributes

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._device.name,
            "manufacturer": "Apple",
            "model": self._device.device_model,
        }
