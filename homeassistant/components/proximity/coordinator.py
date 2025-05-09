"""Data update coordinator for the Proximity integration."""

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import cast

from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_ZONE,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.location import distance

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_TO,
    ATTR_IN_IGNORED_ZONE,
    ATTR_NEAREST,
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DEFAULT_DIR_OF_TRAVEL,
    DEFAULT_DIST_TO_ZONE,
    DEFAULT_NEAREST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type ProximityConfigEntry = ConfigEntry[ProximityDataUpdateCoordinator]


@dataclass
class StateChangedData:
    """StateChangedData class."""

    entity_id: str
    old_state: State | None
    new_state: State | None


@dataclass
class ProximityData:
    """ProximityCoordinatorData class."""

    proximity: dict[str, str | int | None]
    entities: dict[str, dict[str, str | int | None]]


DEFAULT_PROXIMITY_DATA: dict[str, str | int | None] = {
    ATTR_DIST_TO: DEFAULT_DIST_TO_ZONE,
    ATTR_DIR_OF_TRAVEL: DEFAULT_DIR_OF_TRAVEL,
    ATTR_NEAREST: DEFAULT_NEAREST,
}


class ProximityDataUpdateCoordinator(DataUpdateCoordinator[ProximityData]):
    """Proximity data update coordinator."""

    config_entry: ProximityConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ProximityConfigEntry) -> None:
        """Initialize the Proximity coordinator."""
        self.ignored_zone_ids: list[str] = config_entry.data[CONF_IGNORED_ZONES]
        self.tracked_entities: list[str] = config_entry.data[CONF_TRACKED_ENTITIES]
        self.tolerance: int = config_entry.data[CONF_TOLERANCE]
        self.proximity_zone_id: str = config_entry.data[CONF_ZONE]
        self.proximity_zone_name: str = self.proximity_zone_id.split(".")[-1]
        self.unit_of_measurement: str = config_entry.data.get(
            CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit
        )
        self.entity_mapping: dict[str, list[str]] = defaultdict(list)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=None,
        )

        self.data = ProximityData(DEFAULT_PROXIMITY_DATA, {})

        self.state_change_data: StateChangedData | None = None

    @callback
    def async_add_entity_mapping(self, tracked_entity_id: str, entity_id: str) -> None:
        """Add an tracked entity to proximity entity mapping."""
        self.entity_mapping[tracked_entity_id].append(entity_id)

    async def async_check_proximity_state_change(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        self.state_change_data = StateChangedData(
            data["entity_id"], data["old_state"], data["new_state"]
        )
        await self.async_refresh()

    async def async_check_tracked_entity_change(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Fetch and process tracked entity change event."""
        data = event.data
        if data["action"] == "remove":
            self._create_removed_tracked_entity_issue(data["entity_id"])

        if data["action"] == "update" and "entity_id" in data["changes"]:
            old_tracked_entity_id = data["old_entity_id"]
            new_tracked_entity_id = data["entity_id"]

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_TRACKED_ENTITIES: [
                        tracked_entity
                        for tracked_entity in (
                            *self.tracked_entities,
                            new_tracked_entity_id,
                        )
                        if tracked_entity != old_tracked_entity_id
                    ],
                },
            )

    def _calc_distance_to_zone(
        self,
        zone: State,
        device: State,
        latitude: float | None,
        longitude: float | None,
    ) -> int | None:
        if device.state.lower() == self.proximity_zone_name.lower():
            _LOGGER.debug(
                "%s: %s in zone -> distance=0",
                self.name,
                device.entity_id,
            )
            return 0

        if latitude is None or longitude is None:
            _LOGGER.debug(
                "%s: %s has no coordinates -> distance=None",
                self.name,
                device.entity_id,
            )
            return None

        distance_to_centre = distance(
            zone.attributes[ATTR_LATITUDE],
            zone.attributes[ATTR_LONGITUDE],
            latitude,
            longitude,
        )

        # it is ensured, that distance can't be None, since zones must have lat/lon coordinates
        assert distance_to_centre is not None

        zone_radius: float = zone.attributes["radius"]
        if zone_radius > distance_to_centre:
            # we've arrived the zone
            return 0
        return round(distance_to_centre - zone_radius)

    def _calc_direction_of_travel(
        self,
        zone: State,
        device: State,
        old_latitude: float | None,
        old_longitude: float | None,
        new_latitude: float | None,
        new_longitude: float | None,
    ) -> str | None:
        if device.state.lower() == self.proximity_zone_name.lower():
            _LOGGER.debug(
                "%s: %s in zone -> direction_of_travel=arrived",
                self.name,
                device.entity_id,
            )
            return "arrived"

        if (
            old_latitude is None
            or old_longitude is None
            or new_latitude is None
            or new_longitude is None
        ):
            return None

        old_distance = distance(
            zone.attributes[ATTR_LATITUDE],
            zone.attributes[ATTR_LONGITUDE],
            old_latitude,
            old_longitude,
        )
        new_distance = distance(
            zone.attributes[ATTR_LATITUDE],
            zone.attributes[ATTR_LONGITUDE],
            new_latitude,
            new_longitude,
        )

        # it is ensured, that distance can't be None, since zones must have lat/lon coordinates
        assert old_distance is not None
        assert new_distance is not None
        distance_travelled = round(new_distance - old_distance, 1)

        if distance_travelled < self.tolerance * -1:
            return "towards"

        if distance_travelled > self.tolerance:
            return "away_from"

        return "stationary"

    async def _async_update_data(self) -> ProximityData:
        """Calculate Proximity data."""
        if (zone_state := self.hass.states.get(self.proximity_zone_id)) is None:
            _LOGGER.debug(
                "%s: zone %s does not exist -> reset",
                self.name,
                self.proximity_zone_id,
            )
            return ProximityData(DEFAULT_PROXIMITY_DATA, {})

        entities_data = self.data.entities

        # calculate distance for all tracked entities
        for entity_id in self.tracked_entities:
            if (tracked_entity_state := self.hass.states.get(entity_id)) is None:
                if entities_data.pop(entity_id, None) is not None:
                    _LOGGER.debug(
                        "%s: %s does not exist -> remove", self.name, entity_id
                    )
                continue

            if entity_id not in entities_data:
                _LOGGER.debug("%s: %s is new -> add", self.name, entity_id)
                entities_data[entity_id] = {
                    ATTR_DIST_TO: None,
                    ATTR_DIR_OF_TRAVEL: None,
                    ATTR_NAME: tracked_entity_state.name,
                    ATTR_IN_IGNORED_ZONE: False,
                }
            entities_data[entity_id][ATTR_IN_IGNORED_ZONE] = (
                f"{ZONE_DOMAIN}.{tracked_entity_state.state.lower()}"
                in self.ignored_zone_ids
            )
            entities_data[entity_id][ATTR_DIST_TO] = self._calc_distance_to_zone(
                zone_state,
                tracked_entity_state,
                tracked_entity_state.attributes.get(ATTR_LATITUDE),
                tracked_entity_state.attributes.get(ATTR_LONGITUDE),
            )
            if entities_data[entity_id][ATTR_DIST_TO] is None:
                _LOGGER.debug(
                    "%s: %s has unknown distance got -> direction_of_travel=None",
                    self.name,
                    entity_id,
                )
                entities_data[entity_id][ATTR_DIR_OF_TRAVEL] = None

        # calculate direction of travel only for last updated tracked entity
        if (state_change_data := self.state_change_data) is not None and (
            new_state := state_change_data.new_state
        ) is not None:
            _LOGGER.debug(
                "%s: calculate direction of travel for %s",
                self.name,
                state_change_data.entity_id,
            )

            if (old_state := state_change_data.old_state) is not None:
                old_lat = old_state.attributes.get(ATTR_LATITUDE)
                old_lon = old_state.attributes.get(ATTR_LONGITUDE)
            else:
                old_lat = None
                old_lon = None

            entities_data[state_change_data.entity_id][ATTR_DIR_OF_TRAVEL] = (
                self._calc_direction_of_travel(
                    zone_state,
                    new_state,
                    old_lat,
                    old_lon,
                    new_state.attributes.get(ATTR_LATITUDE),
                    new_state.attributes.get(ATTR_LONGITUDE),
                )
            )

        # takeover data for legacy proximity entity
        proximity_data: dict[str, str | int | None] = {
            ATTR_DIST_TO: DEFAULT_DIST_TO_ZONE,
            ATTR_DIR_OF_TRAVEL: DEFAULT_DIR_OF_TRAVEL,
            ATTR_NEAREST: DEFAULT_NEAREST,
        }
        for entity_data in entities_data.values():
            if (distance_to := entity_data[ATTR_DIST_TO]) is None or entity_data[
                ATTR_IN_IGNORED_ZONE
            ]:
                continue

            if isinstance((nearest_distance_to := proximity_data[ATTR_DIST_TO]), str):
                _LOGGER.debug("set first entity_data: %s", entity_data)
                proximity_data = {
                    ATTR_DIST_TO: distance_to,
                    ATTR_DIR_OF_TRAVEL: entity_data[ATTR_DIR_OF_TRAVEL],
                    ATTR_NEAREST: str(entity_data[ATTR_NAME]),
                }
                continue

            if cast(int, nearest_distance_to) > int(distance_to):
                _LOGGER.debug("set closer entity_data: %s", entity_data)
                proximity_data = {
                    ATTR_DIST_TO: distance_to,
                    ATTR_DIR_OF_TRAVEL: entity_data[ATTR_DIR_OF_TRAVEL],
                    ATTR_NEAREST: str(entity_data[ATTR_NAME]),
                }
                continue

            if cast(int, nearest_distance_to) == int(distance_to):
                _LOGGER.debug("set equally close entity_data: %s", entity_data)
                proximity_data[ATTR_NEAREST] = (
                    f"{proximity_data[ATTR_NEAREST]}, {entity_data[ATTR_NAME]!s}"
                )

        return ProximityData(proximity_data, entities_data)

    def _create_removed_tracked_entity_issue(self, entity_id: str) -> None:
        """Create a repair issue for a removed tracked entity."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"tracked_entity_removed_{entity_id}",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.WARNING,
            translation_key="tracked_entity_removed",
            translation_placeholders={"entity_id": entity_id, "name": self.name},
        )
