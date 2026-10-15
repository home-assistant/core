"""Entities for the Person integration."""

from collections.abc import Callable
import logging
from typing import Any, Self, override

from homeassistant.components.device_tracker import (
    DeviceTrackerEntityCapabilityAttribute,
    DeviceTrackerEntityStateAttribute,
    SourceType,
    TrackerEntityStateAttribute,
    TrackingType,
)
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    STATE_HOME,
    EntityStateAttribute,
)
from homeassistant.core import Event, EventStateChangedData, State, callback
from homeassistant.helpers import collection
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_TRACKERS,
    CONF_PICTURE,
    CONF_USER_ID,
    IGNORE_STATES,
    PersonEntityStateAttribute,
)

_LOGGER = logging.getLogger(__package__)


class Person(
    collection.CollectionEntity,
    RestoreEntity,
):
    """Represent a tracked person."""

    _entity_component_unrecorded_attributes = frozenset(
        {PersonEntityStateAttribute.DEVICE_TRACKERS}
    )

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: dict[str, Any]) -> None:
        """Set up person."""
        self._config = config
        self._latitude: float | None = None
        self._longitude: float | None = None
        self._gps_accuracy: float | None = None
        self._source: str | None = None
        self._unsub_track_device: Callable[[], None] | None = None
        self._attr_state: str | None = None
        self.device_trackers: list[str] = []
        self._in_zones: list[str] = []

        self._attr_unique_id = config[CONF_ID]
        self._set_attrs_from_config()

    def _set_attrs_from_config(self) -> None:
        """Set attributes from config."""
        self._attr_name = self._config[CONF_NAME]
        self._attr_entity_picture = self._config.get(CONF_PICTURE)
        self.device_trackers = self._config[CONF_DEVICE_TRACKERS]

    @classmethod
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        person = cls(config)
        person.editable = True
        return person

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        person = cls(config)
        person.editable = False
        return person

    @override
    async def async_added_to_hass(self) -> None:
        """Register device trackers."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._parse_source_state(
                state,
                latitude=state.attributes.get(EntityStateAttribute.LATITUDE),
                longitude=state.attributes.get(EntityStateAttribute.LONGITUDE),
                gps_accuracy=state.attributes.get(
                    PersonEntityStateAttribute.GPS_ACCURACY
                ),
                in_zones=state.attributes.get(PersonEntityStateAttribute.IN_ZONES),
            )

        if self.hass.is_running:
            # Update person now if hass is already running.
            self._async_update_config(self._config)
        else:
            # Wait for hass start to not have race between person
            # and device trackers finishing setup.
            @callback
            def _async_person_start_hass(_: Event) -> None:
                self._async_update_config(self._config)

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, _async_person_start_hass
            )
            # Update extra state attributes now
            # as there are attributes that can already be set
            self._update_extra_state_attributes()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from device trackers when the person is removed."""
        if self._unsub_track_device is not None:
            self._unsub_track_device()
            self._unsub_track_device = None

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._async_update_config(config)

    @callback
    def _async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self._set_attrs_from_config()

        if self._unsub_track_device is not None:
            self._unsub_track_device()
            self._unsub_track_device = None

        if trackers := self._config[CONF_DEVICE_TRACKERS]:
            _LOGGER.debug("Subscribe to device trackers for %s", self.entity_id)

            self._unsub_track_device = async_track_state_change_event(
                self.hass, trackers, self._async_handle_tracker_update
            )

        self._update_state()

    @callback
    def _async_handle_tracker_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle the device tracker state changes."""
        self._update_state()

    @callback
    def _update_state(self) -> None:
        """Update the state."""
        latest_connected = latest_legacy_home = latest_not_home = latest_gps = None
        for entity_id in self._config[CONF_DEVICE_TRACKERS]:
            state = self.hass.states.get(entity_id)

            if not state or state.state in IGNORE_STATES:
                continue

            if state.attributes.get(
                DeviceTrackerEntityCapabilityAttribute.TRACKING_TYPE
            ) == TrackingType.CONNECTION and state.attributes.get(
                DeviceTrackerEntityStateAttribute.IN_ZONES
            ):
                latest_connected = _get_latest(latest_connected, state)
            elif (
                state.attributes.get(DeviceTrackerEntityStateAttribute.SOURCE_TYPE)
                == SourceType.GPS
            ):
                latest_gps = _get_latest(latest_gps, state)
            elif state.state == STATE_HOME:
                # Legacy scanner without tracking type
                latest_legacy_home = _get_latest(latest_legacy_home, state)
            else:
                latest_not_home = _get_latest(latest_not_home, state)

        # A scanner (e.g. a router or beacon) that reports
        # being in a zone is the most reliable presence signal, so it
        # takes precedence over everything else.
        latest = latest_connected or latest_legacy_home or latest_gps or latest_not_home

        if latest:
            self._parse_source_state(
                latest,
                latitude=latest.attributes.get(EntityStateAttribute.LATITUDE),
                longitude=latest.attributes.get(EntityStateAttribute.LONGITUDE),
                gps_accuracy=latest.attributes.get(
                    TrackerEntityStateAttribute.GPS_ACCURACY
                ),
                in_zones=latest.attributes.get(
                    DeviceTrackerEntityStateAttribute.IN_ZONES
                ),
            )
        else:
            self._attr_state = None
            self._source = None
            self._latitude = None
            self._longitude = None
            self._gps_accuracy = None
            self._in_zones = []

        self._update_extra_state_attributes()
        self.async_write_ha_state()

    @callback
    def _parse_source_state(
        self,
        state: State,
        *,
        latitude: float | None,
        longitude: float | None,
        gps_accuracy: int | None,
        in_zones: list[str] | None,
    ) -> None:
        """Set person attributes from a source state.

        The coordinates are read by the caller using the enum matching the
        source, which is either a device tracker or the restored person state.
        An absent ``in_zones`` (``None``) means the source does not report zone
        membership.
        """
        self._attr_state = state.state
        self._source = state.entity_id
        self._latitude = latitude
        self._longitude = longitude
        self._gps_accuracy = gps_accuracy
        self._in_zones = in_zones or []

        # A legacy scanner (one that doesn't report in_zones) reports "home"
        # without zone membership or coordinates. Synthesize home-zone
        # membership and borrow the home zone's coordinates so zone counting,
        # conditions and triggers keep working as they did before the in_zones
        # model was introduced. Modern trackers report in_zones and keep their
        # own (possibly absent) coordinates.
        if (
            in_zones is None
            and state.state == STATE_HOME
            and (home_zone := self.hass.states.get(ENTITY_ID_HOME)) is not None
        ):
            self._in_zones = [ENTITY_ID_HOME]
            if self._latitude is None and self._longitude is None:
                self._latitude = home_zone.attributes.get(EntityStateAttribute.LATITUDE)
                self._longitude = home_zone.attributes.get(
                    EntityStateAttribute.LONGITUDE
                )

    @callback
    def _update_extra_state_attributes(self) -> None:
        """Update extra state attributes."""
        data: dict[str, Any] = {
            PersonEntityStateAttribute.EDITABLE: self.editable,
            PersonEntityStateAttribute.ID: self.unique_id,
            PersonEntityStateAttribute.DEVICE_TRACKERS: self.device_trackers,
            PersonEntityStateAttribute.IN_ZONES: self._in_zones,
        }

        if self._latitude is not None:
            data[EntityStateAttribute.LATITUDE] = self._latitude
        if self._longitude is not None:
            data[EntityStateAttribute.LONGITUDE] = self._longitude
        if self._gps_accuracy is not None:
            data[PersonEntityStateAttribute.GPS_ACCURACY] = self._gps_accuracy
        if self._source is not None:
            data[PersonEntityStateAttribute.SOURCE] = self._source
        if (user_id := self._config.get(CONF_USER_ID)) is not None:
            data[PersonEntityStateAttribute.USER_ID] = user_id

        self._attr_extra_state_attributes = data


def _get_latest(prev: State | None, curr: State) -> State:
    """Get latest state."""
    if prev is None or curr.last_updated > prev.last_updated:
        return curr
    return prev
