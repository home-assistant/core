"""Support for Vilfo Router sensors."""
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_API_DATA_FIELD_BOOT_TIME,
    ATTR_API_DATA_FIELD_LOAD,
    ATTR_BOOT_TIME,
    ATTR_LOAD,
    DOMAIN,
    ROUTER_DEFAULT_MODEL,
    ROUTER_DEFAULT_NAME,
    ROUTER_MANUFACTURER,
)


@dataclass
class VilfoRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class VilfoSensorEntityDescription(SensorEntityDescription, VilfoRequiredKeysMixin):
    """Describes Vilfo sensor entity."""


SENSOR_TYPES: tuple[VilfoSensorEntityDescription, ...] = (
    VilfoSensorEntityDescription(
        key=ATTR_LOAD,
        name="Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        api_key=ATTR_API_DATA_FIELD_LOAD,
    ),
    VilfoSensorEntityDescription(
        key=ATTR_BOOT_TIME,
        name="Boot time",
        icon="mdi:timer-outline",
        api_key=ATTR_API_DATA_FIELD_BOOT_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
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

    def __init__(self, api, description: VilfoSensorEntityDescription) -> None:
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
    def available(self) -> bool:
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

    async def async_update(self) -> None:
        """Update the router data."""
        await self.api.async_update()
        self._attr_native_value = self.api.data.get(self.entity_description.api_key)
