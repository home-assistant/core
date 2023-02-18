"""Philips TV binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""
    coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    if coordinator.api.json_feature_supported("recordings", "List"):
        async_add_entities([PhilipsTVRecordingOngoing(coordinator)])
        async_add_entities([PhilipsTVRecordingNew(coordinator)])


class PhilipsTVRecordingOngoing(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], BinarySensorEntity
):
    """A Philips TV binary sensor, which shows if a recording is ongoing."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_name = f"{coordinator.system['name']} Recording ongoing"
        self._attr_icon = "mdi:record-rec"
        self._attr_unique_id = f"{coordinator.unique_id}_recording_ongoing"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        return True

    @property
    def is_on(self) -> bool:
        """Return True if at least one recording is ongoing."""
        for rec in self.coordinator.api.recordings_list["recordings"]:
            if rec["RecordingType"] == "RECORDING_ONGOING":
                return True
        return False


class PhilipsTVRecordingNew(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], BinarySensorEntity
):
    """A Philips TV binary sensor, which shows if a new recording is available."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_name = f"{coordinator.system['name']} New recording available"
        self._attr_icon = "mdi:new-box"
        self._attr_unique_id = f"{coordinator.unique_id}_recording_new"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if not super().available:
            return False
        return True

    @property
    def is_on(self) -> bool:
        """Return True if at least one recording is new."""
        for rec in self.coordinator.api.recordings_list["recordings"]:
            if rec["RecordingType"] == "RECORDING_NEW":
                return True
        return False
