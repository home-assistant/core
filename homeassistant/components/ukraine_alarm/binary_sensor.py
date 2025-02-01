"""binary sensors for Ukraine Alarm integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALERT_TYPE_AIR,
    ALERT_TYPE_ARTILLERY,
    ALERT_TYPE_CHEMICAL,
    ALERT_TYPE_NUCLEAR,
    ALERT_TYPE_UNKNOWN,
    ALERT_TYPE_URBAN_FIGHTS,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import UkraineAlarmDataUpdateCoordinator

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=ALERT_TYPE_UNKNOWN,
        translation_key="unknown",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_AIR,
        translation_key="air",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_URBAN_FIGHTS,
        translation_key="urban_fights",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_ARTILLERY,
        translation_key="artillery",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_CHEMICAL,
        translation_key="chemical",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    BinarySensorEntityDescription(
        key=ALERT_TYPE_NUCLEAR,
        translation_key="nuclear",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ukraine Alarm binary sensor entities based on a config entry."""
    name = config_entry.data[CONF_NAME]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        UkraineAlarmSensor(
            name,
            config_entry.unique_id,
            description,
            coordinator,
        )
        for description in BINARY_SENSOR_TYPES
    )


class UkraineAlarmSensor(
    CoordinatorEntity[UkraineAlarmDataUpdateCoordinator], BinarySensorEntity
):
    """Class for a Ukraine Alarm binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        name,
        unique_id,
        description: BinarySensorEntityDescription,
        coordinator: UkraineAlarmDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{unique_id}-{description.key}".lower()
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=name,
            configuration_url="https://siren.pp.ua/",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.get(self.entity_description.key, None)
