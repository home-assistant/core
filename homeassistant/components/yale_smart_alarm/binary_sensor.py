"""Binary sensors for Yale Alarm."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, MANUFACTURER, MODEL
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale binary sensor entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    async_add_entities(
        YaleBinarySensor(coordinator, data) for data in coordinator.data["door_windows"]
    )


class YaleBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Yale binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator: YaleDataUpdateCoordinator, data: dict) -> None:
        """Initialize the Yale Lock Device."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_name = data["name"]
        self._attr_unique_id = data["address"]
        self._attr_device_info = DeviceInfo(
            name=self._attr_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            identifiers={(DOMAIN, data["address"])},
            via_device=(DOMAIN, self._coordinator.entry.data[CONF_USERNAME]),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        for contact in self.coordinator.data["door_windows"]:
            return bool(
                contact["address"] == self._attr_unique_id
                and contact["_state"] == "open"
            )
        return None
