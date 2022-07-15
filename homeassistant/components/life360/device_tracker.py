"""Support for Life360 device tracking."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_CHARGING
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_ADDRESS,
    ATTR_AT_LOC_SINCE,
    ATTR_DRIVING,
    ATTR_LAST_SEEN,
    ATTR_PLACE,
    ATTR_SPEED,
    ATTR_WIFI_ON,
    ATTRIBUTION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    DOMAIN,
    LOGGER,
    SHOW_DRIVING,
)

_LOC_ATTRS = (
    "address",
    "at_loc_since",
    "driving",
    "gps_accuracy",
    "last_seen",
    "latitude",
    "longitude",
    "place",
    "speed",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the device tracker platform."""
    coordinator = hass.data[DOMAIN].coordinators[entry.entry_id]
    tracked_members = hass.data[DOMAIN].tracked_members
    logged_circles = hass.data[DOMAIN].logged_circles
    logged_places = hass.data[DOMAIN].logged_places

    @callback
    def process_data(new_members_only: bool = True) -> None:
        """Process new Life360 data."""
        for circle_id, circle in coordinator.data.circles.items():
            if circle_id not in logged_circles:
                logged_circles.append(circle_id)
                LOGGER.debug("Circle: %s", circle.name)

            new_places = []
            for place_id, place in circle.places.items():
                if place_id not in logged_places:
                    logged_places.append(place_id)
                    new_places.append(place)
            if new_places:
                msg = f"Places from {circle.name}:"
                for place in new_places:
                    msg += f"\n- name: {place.name}"
                    msg += f"\n  latitude: {place.latitude}"
                    msg += f"\n  longitude: {place.longitude}"
                    msg += f"\n  radius: {place.radius}"
                LOGGER.debug(msg)

        new_entities = []
        for member_id, member in coordinator.data.members.items():
            tracked_by_entry = tracked_members.get(member_id)
            if new_member := not tracked_by_entry:
                tracked_members[member_id] = entry.entry_id
                LOGGER.debug("Member: %s (%s)", member.name, entry.unique_id)
            if (
                new_member
                or tracked_by_entry == entry.entry_id
                and not new_members_only
            ):
                new_entities.append(Life360DeviceTracker(coordinator, member_id))
        if new_entities:
            async_add_entities(new_entities)

    process_data(new_members_only=False)
    entry.async_on_unload(coordinator.async_add_listener(process_data))


class Life360DeviceTracker(CoordinatorEntity, TrackerEntity):
    """Life360 Device Tracker."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: DataUpdateCoordinator, member_id: str) -> None:
        """Initialize Life360 Entity."""
        super().__init__(coordinator)
        self._attr_unique_id = member_id

        self._data = coordinator.data.members[self.unique_id]

        self._attr_name = self._data.name
        self._attr_entity_picture = self._data.entity_picture

        self._prev_data = self._data

    @property
    def _options(self) -> Mapping[str, Any]:
        """Shortcut to config entry options."""
        return cast(Mapping[str, Any], self.coordinator.config_entry.options)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get a shortcut to this member's data. Can't guarantee it's the same dict every
        # update, or that there is even data for this member every update, so need to
        # update shortcut each time.
        self._data = self.coordinator.data.members.get(self.unique_id)

        if self.available:
            # If nothing important has changed, then skip the update altogether.
            if self._data == self._prev_data:
                return

            # Check if we should effectively throw out new location data.
            last_seen = self._data.last_seen
            prev_seen = self._prev_data.last_seen
            max_gps_acc = self._options.get(CONF_MAX_GPS_ACCURACY)
            bad_last_seen = last_seen < prev_seen
            bad_accuracy = (
                max_gps_acc is not None and self.location_accuracy > max_gps_acc
            )
            if bad_last_seen or bad_accuracy:
                if bad_last_seen:
                    LOGGER.warning(
                        "%s: Ignoring location update because "
                        "last_seen (%s) < previous last_seen (%s)",
                        self.entity_id,
                        last_seen,
                        prev_seen,
                    )
                if bad_accuracy:
                    LOGGER.warning(
                        "%s: Ignoring location update because "
                        "expected GPS accuracy (%0.1f) is not met: %i",
                        self.entity_id,
                        max_gps_acc,
                        self.location_accuracy,
                    )
                # Overwrite new location related data with previous values.
                for attr in _LOC_ATTRS:
                    setattr(self._data, attr, getattr(self._prev_data, attr))

            self._prev_data = self._data

        super()._handle_coordinator_update()

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Guard against member not being in last update for some reason.
        return super().available and self._data is not None

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if self.available:
            self._attr_entity_picture = self._data.entity_picture
        return super().entity_picture

    # All of the following will only be called if self.available is True.

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self._data.battery_level

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        return self._data.gps_accuracy

    @property
    def driving(self) -> bool:
        """Return if driving."""
        if (driving_speed := self._options.get(CONF_DRIVING_SPEED)) is not None:
            if self._data.speed >= driving_speed:
                return True
        return self._data.driving

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        if self._options.get(SHOW_DRIVING) and self.driving:
            return "Driving"
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self._data.latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self._data.longitude

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {}
        attrs[ATTR_ADDRESS] = self._data.address
        attrs[ATTR_AT_LOC_SINCE] = self._data.at_loc_since
        attrs[ATTR_BATTERY_CHARGING] = self._data.battery_charging
        attrs[ATTR_DRIVING] = self.driving
        attrs[ATTR_LAST_SEEN] = self._data.last_seen
        attrs[ATTR_PLACE] = self._data.place
        attrs[ATTR_SPEED] = self._data.speed
        attrs[ATTR_WIFI_ON] = self._data.wifi_on
        return attrs
