"""The Things Network's integration binary sensors."""

import logging

from ttn_client import TTNDeviceTrackerValue

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_APP_ID, DOMAIN
from .entity import TTNEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add binary sensors for TTN."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    trackers: set[tuple[str, str]] = set()

    def _async_measurement_listener() -> None:
        data = coordinator.data
        new_trackers = {
            (device_id, field_id): TtnTracker(
                coordinator,
                entry.data[CONF_APP_ID],
                ttn_value,
            )
            for device_id, device_uplinks in data.items()
            for field_id, ttn_value in device_uplinks.items()
            if (device_id, field_id) not in trackers
            and isinstance(ttn_value, TTNDeviceTrackerValue)
        }
        if len(new_trackers):
            async_add_entities(new_trackers.values())
        trackers.update(new_trackers.keys())

    entry.async_on_unload(coordinator.async_add_listener(_async_measurement_listener))
    _async_measurement_listener()


class TtnTracker(TTNEntity, TrackerEntity):
    """Represents a TTN Home Assistant Sensor."""

    _ttn_value: TTNDeviceTrackerValue

    @property
    def source_type(self) -> SourceType:
        """Return source_type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._ttn_value.latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._ttn_value.longitude

    @property
    def altitude(self) -> float | None:
        """Return altitude value of the device."""
        return self._ttn_value.altitude
