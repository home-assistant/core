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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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


@dataclass(frozen=True, kw_only=True)
class VilfoSensorEntityDescription(SensorEntityDescription):
    """Describes Vilfo sensor entity."""

    api_key: str


SENSOR_TYPES: tuple[VilfoSensorEntityDescription, ...] = (
    VilfoSensorEntityDescription(
        key=ATTR_LOAD,
        translation_key=ATTR_LOAD,
        native_unit_of_measurement=PERCENTAGE,
        api_key=ATTR_API_DATA_FIELD_LOAD,
    ),
    VilfoSensorEntityDescription(
        key=ATTR_BOOT_TIME,
        translation_key=ATTR_BOOT_TIME,
        api_key=ATTR_API_DATA_FIELD_BOOT_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Vilfo Router entities from a config_entry."""
    vilfo = hass.data[DOMAIN][config_entry.entry_id]

    entities = [VilfoRouterSensor(vilfo, description) for description in SENSOR_TYPES]

    async_add_entities(entities, True)


class VilfoRouterSensor(SensorEntity):
    """Define a Vilfo Router Sensor."""

    entity_description: VilfoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, api, description: VilfoSensorEntityDescription) -> None:
        """Initialize."""
        self.entity_description = description
        self.api = api
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, api.host, api.mac_address)},  # type: ignore[arg-type]
            name=ROUTER_DEFAULT_NAME,
            manufacturer=ROUTER_MANUFACTURER,
            model=ROUTER_DEFAULT_MODEL,
            sw_version=api.firmware_version,
        )
        self._attr_unique_id = f"{api.unique_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return whether the sensor is available or not."""
        return self.api.available

    async def async_update(self) -> None:
        """Update the router data."""
        await self.api.async_update()
        self._attr_native_value = self.api.data.get(self.entity_description.api_key)
