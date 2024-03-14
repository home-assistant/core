"""The Things Network's integration device trackers."""


from typing import Any

from ttn_client import TTNBaseValue, TTNDeviceTrackerValue

from homeassistant.components import zone
from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import OPTIONS_FIELD_ENTITY_TYPE_DEVICE_TRACKER
from .entity import TTN_Entity
from .entry_settings import TTN_EntrySettings


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add entities for TTN."""

    coordinator = TTN_EntrySettings(entry).get_coordinator()
    coordinator.register_platform_entity_class(TtnDeviceTracker, async_add_entities)
    coordinator.async_add_entities()


async def async_unload_entry(hass: HomeAssistant, entry, async_remove_entity) -> None:
    """Handle removal of an entry."""


class TtnDeviceTracker(TTN_Entity, TrackerEntity):
    """Represents a TTN Home Assistant BinarySensor."""

    @staticmethod
    def manages_uplink(entrySettings: TTN_EntrySettings, ttn_value: TTNBaseValue):
        """Check if this class maps to this ttn_value."""

        entity_type = entrySettings.get_entity_type(
            ttn_value.device_id, ttn_value.field_id
        )

        if entity_type:
            return entity_type == OPTIONS_FIELD_ENTITY_TYPE_DEVICE_TRACKER
        return isinstance(ttn_value, TTNDeviceTrackerValue)

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return 0

    @property
    def location_name(self) -> str:
        """Return a location name for the current location of the device."""
        return None

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._state["latitude"]

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._state["longitude"]

    @property
    def altitude(self) -> float:
        """Return altitude value of the device."""
        return self._state["altitude"]

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        if self.location_name:
            return self.location_name

        if self._state["latitude"] > 0:
            zone_state = zone.async_active_zone(
                self.hass, self.latitude, self.longitude, self.location_accuracy
            )
            if zone_state is None:
                state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                state = STATE_HOME
            else:
                state = zone_state.name
            return state

        return None

    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        attr = {}
        attr.update(super().state_attributes)
        if self.latitude is not None:
            attr[ATTR_LATITUDE] = self.latitude
            attr[ATTR_LONGITUDE] = self.longitude
            attr[ATTR_GPS_ACCURACY] = self.location_accuracy
            attr["altitude"] = self.altitude

        return attr
