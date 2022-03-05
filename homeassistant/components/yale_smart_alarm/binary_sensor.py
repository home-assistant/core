"""Binary sensors for Yale Alarm."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, MANUFACTURER, MODEL
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleEntity

SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="acfail",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Powerloss",
    ),
    BinarySensorEntityDescription(
        key="battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Battery",
    ),
    BinarySensorEntityDescription(
        key="tamper",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Tamper",
    ),
    BinarySensorEntityDescription(
        key="jam",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Jam",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale binary sensor entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    async_add_entities(
        YaleDoorSensor(coordinator, data) for data in coordinator.data["door_windows"]
    )

    async_add_entities(
        YaleProblemSensor(coordinator, description) for description in SENSOR_TYPES
    )


class YaleDoorSensor(YaleEntity, BinarySensorEntity):
    """Representation of a Yale door sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["sensor_map"][self._attr_unique_id] == "open"


class YaleProblemSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Yale problem sensor."""

    entity_description: BinarySensorEntityDescription
    coordinator: YaleDataUpdateCoordinator

    def __init__(
        self,
        coordinator: YaleDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initiate Yale Problem Sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_name = (
            f"{coordinator.entry.data[CONF_NAME]} {entity_description.name}"
        )
        self._attr_unique_id = f"{coordinator.entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.data[CONF_USERNAME])},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.entry.data[CONF_NAME],
            connections={
                (CONNECTION_NETWORK_MAC, coordinator.data["panel_info"]["mac"])
            },
            sw_version=coordinator.data["panel_info"]["version"],
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return (
            self.coordinator.data["status"][self.entity_description.key]
            != "main.normal"
        )
