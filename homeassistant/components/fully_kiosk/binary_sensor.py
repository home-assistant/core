"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator

SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="kioskMode", name="Kiosk mode", entity_category=EntityCategory.DIAGNOSTIC
    ),
    BinarySensorEntityDescription(
        key="plugged",
        name="Plugged in",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="isDeviceAdmin",
        name="Device admin",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        FullyBinarySensor(coordinator, description)
        for description in SENSORS
        if description.key in coordinator.data
    )


class FullyBinarySensor(
    CoordinatorEntity[FullyKioskDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Fully Kiosk Browser binary sensor."""

    _attr_has_entity_name: bool = True

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        self._sensor = description.key

        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.data["deviceID"])},
            "name": coordinator.data["deviceName"],
            "manufacturer": coordinator.data["deviceManufacturer"],
            "model": coordinator.data["deviceModel"],
            "sw_version": coordinator.data["appVersionName"],
            "configuration_url": f"http://{coordinator.data['ip4']}:2323",
        }
        super().__init__(coordinator)

    @property
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on."""
        return self.coordinator.data.get(self._sensor)
