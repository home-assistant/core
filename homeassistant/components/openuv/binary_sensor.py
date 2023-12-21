"""Support for OpenUV binary sensors."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import as_local, parse_datetime, utcnow

from . import OpenUvEntity
from .const import DATA_PROTECTION_WINDOW, DOMAIN, LOGGER, TYPE_PROTECTION_WINDOW
from .coordinator import OpenUvCoordinator

ATTR_PROTECTION_WINDOW_ENDING_TIME = "end_time"
ATTR_PROTECTION_WINDOW_ENDING_UV = "end_uv"
ATTR_PROTECTION_WINDOW_STARTING_TIME = "start_time"
ATTR_PROTECTION_WINDOW_STARTING_UV = "start_uv"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up an OpenUV sensor based on a config entry."""
    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ProtectionWindowBinarySensor(
                coordinators[DATA_PROTECTION_WINDOW],
                # We inline a simple entity description here because this entity will
                # still inherit from OpenUvEntity (which requires a description):
                BinarySensorEntityDescription(key=TYPE_PROTECTION_WINDOW),
            )
        ]
    )


@dataclass(frozen=True)
class ProtectionWindow:
    """Define a protection window."""

    from_dt_utc: datetime
    to_dt_utc: datetime


class ProtectionWindowBoundary(StrEnum):
    """Define a protection window boundary."""

    START = "start"
    END = "end"


@dataclass
class ScheduledProtectionWindowStateChange:
    """Define a representation of a scheduled protection window state change."""

    hass: HomeAssistant
    boundary: ProtectionWindowBoundary
    target: datetime
    update_state_method: Callable[[datetime], None]
    _unsub_state_change_callback: CALLBACK_TYPE | None = None

    @callback
    def async_deregister(self) -> None:
        """Deregister the scheduled state change."""
        if self._unsub_state_change_callback:
            self._unsub_state_change_callback()
            self._unsub_state_change_callback = None

    @callback
    def async_schedule(self, target: datetime) -> None:
        """Schedule the state change."""
        if self._unsub_state_change_callback and target == self.target:
            # If a state change has already been scheduled for the same datetime, just
            # return:
            return

        LOGGER.debug(
            "Scheduling a protection window state change: %s (%s)",
            self.boundary,
            self.target,
        )
        if self._unsub_state_change_callback:
            self._unsub_state_change_callback()
        self._unsub_state_change_callback = async_track_point_in_utc_time(
            self.hass, self.update_state_method, self.target
        )


class ProtectionWindowBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    _attr_icon = "mdi:sunglasses"
    _attr_translation_key = "protection_window"

    def __init__(
        self, coordinator: OpenUvCoordinator, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        self._scheduled_state_changes: dict[
            ProtectionWindowBoundary, ScheduledProtectionWindowStateChange
        ] = {}

    @callback
    def _get_current_window(self) -> ProtectionWindow | None:
        """Get the current window start/end datetimes (if they exist) from data."""
        from_dt_raw = self.coordinator.data["from_time"]
        to_dt_raw = self.coordinator.data["to_time"]

        if from_dt_raw is None or to_dt_raw is None:
            LOGGER.debug("Not in a protection window")
            return None

        from_dt_utc = parse_datetime(self.coordinator.data["from_time"])
        to_dt_utc = parse_datetime(self.coordinator.data["to_time"])

        if from_dt_utc is None or to_dt_utc is None:
            LOGGER.warning("Protection window data cannot be parsed")
            return None

        return ProtectionWindow(from_dt_utc=from_dt_utc, to_dt_utc=to_dt_utc)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            ATTR_PROTECTION_WINDOW_ENDING_UV: self.coordinator.data["to_uv"],
            ATTR_PROTECTION_WINDOW_STARTING_UV: self.coordinator.data["from_uv"],
        }

        if window := self._get_current_window():
            attrs[ATTR_PROTECTION_WINDOW_ENDING_TIME] = as_local(window.to_dt_utc)
            attrs[ATTR_PROTECTION_WINDOW_STARTING_TIME] = as_local(window.from_dt_utc)
        else:
            attrs[ATTR_PROTECTION_WINDOW_ENDING_TIME] = None
            attrs[ATTR_PROTECTION_WINDOW_STARTING_TIME] = None

        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if (window := self._get_current_window()) is None:
            return False
        return window.from_dt_utc <= utcnow() <= window.to_dt_utc

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        @callback
        def async_update_state(_: datetime) -> None:
            """Update the entity state."""
            self.async_write_ha_state()

        @callback
        def async_schedule_state_change(
            boundary: ProtectionWindowBoundary, target: datetime
        ) -> None:
            """Schedule an entity state change based upon a datetime."""
            if (state_change := self._scheduled_state_changes.get(boundary)) is None:
                state_change = self._scheduled_state_changes[
                    boundary
                ] = ScheduledProtectionWindowStateChange(
                    hass=self.hass,
                    boundary=boundary,
                    target=target,
                    update_state_method=async_update_state,
                )

            state_change.async_schedule(target)

        @callback
        def async_schedule_state_changes() -> None:
            """Schedule protection window state updates."""
            if (window := self._get_current_window()) is None:
                return

            now = utcnow()
            if now < window.from_dt_utc:
                async_schedule_state_change(
                    ProtectionWindowBoundary.START, window.from_dt_utc
                )
            if now < window.to_dt_utc:
                async_schedule_state_change(
                    ProtectionWindowBoundary.END, window.to_dt_utc
                )

        self.async_on_remove(
            self.coordinator.async_add_listener(async_schedule_state_changes)
        )

        async_schedule_state_changes()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        for state_change in self._scheduled_state_changes.values():
            state_change.async_deregister()
        self._scheduled_state_changes = {}
