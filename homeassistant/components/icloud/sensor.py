"""Support for iCloud sensors."""
import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, DEVICE_CLASS_BATTERY
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import HomeAssistantType

from .account import IcloudDevice
from .const import DOMAIN, SERVICE_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up iCloud devices sensors based on a config entry."""
    username = entry.data[CONF_USERNAME]

    entities = []
    for device in hass.data[DOMAIN][username].devices.values():
        if device.battery_level is not None:
            _LOGGER.debug("Adding battery sensor for %s", device.name)
            entities.append(IcloudDeviceBatterySensor(device))

    async_add_entities(entities, True)


class IcloudDeviceBatterySensor(Entity):
    """Representation of a iCloud device battery sensor."""

    def __init__(self, device: IcloudDevice):
        """Initialize the battery sensor."""
        self._device = device
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._device.unique_id}_battery"

    @property
    def name(self) -> str:
        """Sensor name."""
        return f"{self._device.name} battery state"

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
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "name": self._device.name,
            "manufacturer": "Apple",
            "model": self._device.device_model,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, SERVICE_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()
