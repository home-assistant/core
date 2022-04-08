"""Support for Vilfo Router sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ROUTER_DEFAULT_MODEL,
    ROUTER_DEFAULT_NAME,
    ROUTER_MANUFACTURER,
    SENSOR_TYPES,
    VilfoSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Vilfo Router entities from a config_entry."""
    vilfo = hass.data[DOMAIN][config_entry.entry_id]

    entities = [VilfoRouterSensor(vilfo, description) for description in SENSOR_TYPES]

    async_add_entities(entities, True)


class VilfoRouterSensor(SensorEntity):
    """Define a Vilfo Router Sensor."""

    entity_description: VilfoSensorEntityDescription

    def __init__(self, api, description: VilfoSensorEntityDescription):
        """Initialize."""
        self.entity_description = description
        self.api = api
        self._device_info = {
            "identifiers": {(DOMAIN, api.host, api.mac_address)},
            "name": ROUTER_DEFAULT_NAME,
            "manufacturer": ROUTER_MANUFACTURER,
            "model": ROUTER_DEFAULT_MODEL,
            "sw_version": api.firmware_version,
        }
        self._attr_unique_id = f"{api.unique_id}_{description.key}"

    @property
    def available(self):
        """Return whether the sensor is available or not."""
        return self.api.available

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def name(self):
        """Return the name of the sensor."""
        parent_device_name = self._device_info["name"]
        return f"{parent_device_name} {self.entity_description.name}"

    async def async_update(self):
        """Update the router data."""
        await self.api.async_update()
        self._attr_native_value = self.api.data.get(self.entity_description.api_key)
