"""Philips TV sensors."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

MAX_UNIX_TIME = 2147483647


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
        async_add_entities([PhilipsTVRecordingTimeNext(coordinator)])


class PhilipsTVRecordingTimeNext(
    CoordinatorEntity[PhilipsTVDataUpdateCoordinator], SensorEntity
):
    """A Philips TV sensor, which shows the next scheduled recording."""

    def __init__(
        self,
        coordinator: PhilipsTVDataUpdateCoordinator,
    ) -> None:
        """Initialize entity."""

        super().__init__(coordinator)

        self._attr_name = f"{coordinator.system['name']} Next scheduled recording time"
        self._attr_icon = "mdi:clipboard-text-clock"
        self._attr_unique_id = f"{coordinator.unique_id}_recording_schedule_next_time"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, coordinator.unique_id),
            }
        )
        self.next_time = MAX_UNIX_TIME

    @property
    def native_value(self) -> datetime | None:
        """Return sensor state."""
        for rec in self.coordinator.api.recordings_list["recordings"]:
            if rec["RecordingType"] == "RECORDING_SCHEDULED":
                rec_time_planned = rec["StartTime"]
                rec_margin_start = rec["MarginStart"]
                rec_time = rec_time_planned - rec_margin_start

                if rec_time < self.next_time:
                    self.next_time = rec_time

        if self.next_time == MAX_UNIX_TIME:
            return None

        return datetime.fromtimestamp(self.next_time, tz=timezone.utc)
