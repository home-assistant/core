"""Philips TV binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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

    if (
        coordinator.api.json_feature_supported("recordings", "List")
        and coordinator.api.api_version == 6
    ):
        async_add_entities([PhilipsTVRecordingOngoing(coordinator)])
        async_add_entities([PhilipsTVRecordingNew(coordinator)])


def _check_for_one(self, entry, value) -> bool:
    """Return True if at least one specified value is available within entry of list."""
    for rec in self.coordinator.api.recordings_list["recordings"]:
        if rec[entry] == value:
            return True
    return False


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

        self._attr_has_entity_name = True
        self._attr_translation_key = "recording_ongoing"
        self._attr_icon = "mdi:record-rec"
        self._attr_unique_id = f"{coordinator.unique_id}_recording_ongoing"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    def _update_from_coordinator(self):
        """Set is_on true if at least one recording is ongoing."""
        self._attr_is_on = _check_for_one(self, "RecordingType", "RECORDING_ONGOING")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()


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

        self._attr_has_entity_name = True
        self._attr_translation_key = "recording_new"
        self._attr_icon = "mdi:new-box"
        self._attr_unique_id = f"{coordinator.unique_id}_recording_new"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )

    def _update_from_coordinator(self):
        """Set is_on true if at least one recording is new."""
        self._attr_is_on = _check_for_one(self, "RecordingType", "RECORDING_NEW")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()
