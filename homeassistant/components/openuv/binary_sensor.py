"""Support for OpenUV binary sensors."""
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
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
                # still inherit from OpenUvEntity, which requires an entity description
                # to be defined:
                BinarySensorEntityDescription(key=TYPE_PROTECTION_WINDOW),
            )
        ]
    )


@dataclass
class ProtectionWindow:
    """Define a protection window."""

    from_dt_utc: datetime
    to_dt_utc: datetime


class ProtectionWindowBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    _attr_icon = "mdi:sunglasses"
    _attr_translation_key = "protection_window"

    COORDINATOR_KEYS = ("from_time", "to_time")
    COORDINATOR_RETRIES = 3

    def __init__(
        self, coordinator: OpenUvCoordinator, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        self._coordinator_retries = 0
        self._unsub_coordinator_retry: CALLBACK_TYPE | None = None

    @callback
    def _get_current_window(self) -> ProtectionWindow | None:
        """Get the current window start/end datetimes (if they exist) from data."""
        if not all(
            self.coordinator.data.get(key) is not None for key in self.COORDINATOR_KEYS
        ):
            LOGGER.debug("Cannot find protection window data keys in coordinator")
            return None

        from_dt_raw = self.coordinator.data["from_time"]
        to_dt_raw = self.coordinator.data["to_time"]

        if from_dt_raw is None or to_dt_raw is None:
            LOGGER.debug("Protection window data values are invalid")
            return None

        from_dt_utc = parse_datetime(from_dt_raw)
        to_dt_utc = parse_datetime(to_dt_raw)

        if from_dt_utc is None or to_dt_utc is None:
            LOGGER.debug("Protection window data cannot be parsed")
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

        async def async_request_coordinator_refresh(_: datetime) -> None:
            """Request a coordinator refresh."""
            await self.coordinator.async_request_refresh()

        @callback
        def async_schedule_state_change(target: datetime) -> None:
            """Schedule an entity state change based upon a datetime."""
            LOGGER.debug("Scheduling a protection window state change at %s", target)
            self.async_on_remove(
                async_track_point_in_utc_time(self.hass, async_update_state, target)
            )

        @callback
        def async_schedule_state_changes() -> None:
            """Schedule protection window state updates."""
            if (window := self._get_current_window()) is None:
                # Sometimes, the OpenUV API can hiccup and fail to return protection
                # window data. If that happens, we should try a few more times
                # (properly spaced out) before giving up:
                if self._coordinator_retries < self.COORDINATOR_RETRIES:
                    self._coordinator_retries += 1
                    target_dt = utcnow() + timedelta(hours=1)

                    LOGGER.debug(
                        "Retrying protection window state schedule at %s (attempt %s of %s)",
                        target_dt,
                        self._coordinator_retries + 1,
                        self.COORDINATOR_RETRIES,
                    )

                    if self._unsub_coordinator_retry:
                        self._unsub_coordinator_retry()
                    self._unsub_coordinator_retry = async_track_point_in_utc_time(
                        self.hass, async_request_coordinator_refresh, target_dt
                    )
                else:
                    LOGGER.debug(
                        "Skipping protection window state schedule (%s retries)",
                        self.COORDINATOR_RETRIES,
                    )
                    self._coordinator_retries = 0
                return

            now = utcnow()
            if now < window.from_dt_utc:
                async_schedule_state_change(window.from_dt_utc)
                async_schedule_state_change(window.to_dt_utc)
            elif now < window.to_dt_utc:
                async_schedule_state_change(window.to_dt_utc)

        self.async_on_remove(
            self.coordinator.async_add_listener(async_schedule_state_changes)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unsub_coordinator_retry:
            self._unsub_coordinator_retry()
