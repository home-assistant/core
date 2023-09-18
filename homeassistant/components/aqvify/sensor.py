"""Support for Aqvify sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_NAME, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import CONF_DEVICE_KEY, DOMAIN, LOGGER, MIN_TIME_BETWEEN_UPDATES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aqvify sensors based on a config entry."""

    sensors: list[Entity] = [
        AqvifyWaterLevelMeter(device, entry) for device in entry.data[CONF_DEVICES]
    ]

    async_add_entities(sensors)


class AqvifyWaterLevelMeter(SensorEntity):
    """Representation of a Aqvify water level meter."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device, entry) -> None:
        """Initialize the sensor."""
        super().__init__()
        self._attr_name = device[CONF_NAME]
        self._attr_unique_id = f"{device[CONF_DEVICE_KEY]}-water_level"
        self.device_key = device[CONF_DEVICE_KEY]
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name=f"{self.name} - Water Level",
            manufacturer="Aqvify",
            identifiers={(DOMAIN, self.device_key)},
            configuration_url="https://app.aqvify.com/",
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Update sensor value."""
        LOGGER.debug("Updating %s", self.device_key)

        try:
            latest_value = self.hass.data[DOMAIN][self.entry.entry_id].get_latest_value(
                self.device_key
            )

            self._attr_native_value = round(latest_value["waterLevel"], 2)
        except Exception:  # pylint: disable=broad-except
            LOGGER.debug("Unexpected response from Aqvify, %s", Exception)
