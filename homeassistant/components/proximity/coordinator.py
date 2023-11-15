"""Data update coordinator for the Proximity integration."""

from dataclasses import dataclass
import logging
from typing import TypedDict

from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICES,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_ZONE,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.location import distance
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    DEFAULT_DIR_OF_TRAVEL,
    DEFAULT_DIST_TO_ZONE,
    DEFAULT_NEAREST,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class StateChangedData:
    """StateChangedData class."""

    entity_id: str
    old_state: State | None
    new_state: State | None


class ProximityData(TypedDict):
    """ProximityData type class."""

    dist_to_zone: str | float
    dir_of_travel: str | float
    nearest: str


class ProximityDataUpdateCoordinator(DataUpdateCoordinator[ProximityData]):
    """Proximity data update coordinator."""

    def __init__(
        self, hass: HomeAssistant, friendly_name: str, config: ConfigType
    ) -> None:
        """Initialize the Proximity coordinator."""
        self.ignored_zones: list[str] = config[CONF_IGNORED_ZONES]
        self.proximity_devices: list[str] = config[CONF_DEVICES]
        self.tolerance: int = config[CONF_TOLERANCE]
        self.proximity_zone: str = config[CONF_ZONE]
        self.unit_of_measurement: str = config.get(
            CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit
        )
        self.friendly_name = friendly_name

        super().__init__(
            hass,
            _LOGGER,
            name=friendly_name,
            update_interval=None,
        )

        self.data = {
            "dist_to_zone": DEFAULT_DIST_TO_ZONE,
            "dir_of_travel": DEFAULT_DIR_OF_TRAVEL,
            "nearest": DEFAULT_NEAREST,
        }
        self.state_change_data: StateChangedData | None = None

    async def async_check_proximity_state_change(
        self, entity: str, old_state: State | None, new_state: State | None
    ) -> None:
        """Fetch and process state change event."""
        self.state_change_data = StateChangedData(entity, old_state, new_state)
        await self.async_refresh()

    async def _async_update_data(self) -> ProximityData:
        """Calculate Proximity data."""
        if (state_change_data := self.state_change_data) is None:
            return self.data

        # no new_state, entity has been removed
        if state_change_data.new_state is None:
            # both old and new can't be None
            assert state_change_data.old_state is not None

            remaining_devices = [
                device
                for device in self.proximity_devices
                if device.lower() != state_change_data.entity_id
            ]

            # just some entity has been removed
            if (
                remaining_devices
                and state_change_data.old_state.name not in self.data["nearest"]
            ):
                _LOGGER.debug(
                    "%s: %s has been removed -> abort",
                    self.friendly_name,
                    state_change_data.entity_id,
                )
                return self.data

            # the nearest entity has been removed
            if (
                remaining_devices
                and self.data["nearest"] == state_change_data.old_state.name
            ):
                _LOGGER.debug(
                    "%s: %s has been removed, but was the nearest -> reset",
                    self.friendly_name,
                    state_change_data.entity_id,
                )
                return {
                    "dist_to_zone": DEFAULT_DIST_TO_ZONE,
                    "dir_of_travel": DEFAULT_DIR_OF_TRAVEL,
                    "nearest": DEFAULT_NEAREST,
                }

            # one of the nearest entities has been removed
            if (
                remaining_devices
                and state_change_data.old_state.name in self.data["nearest"]
            ):
                _LOGGER.debug(
                    "%s: %s has been removed, but was in nearest -> remove from nearest",
                    self.friendly_name,
                    state_change_data.entity_id,
                )
                new_nearest = [
                    device
                    for device in self.data["nearest"].split(", ")
                    if device != state_change_data.old_state.name
                ]
                return {
                    "dist_to_zone": self.data["dist_to_zone"],
                    "dir_of_travel": self.data["dir_of_travel"],
                    "nearest": ", ".join(new_nearest),
                }

            # last tracked entity has been removed
            _LOGGER.debug(
                "%s: last tracked device has been removed -> reset",
                self.friendly_name,
            )
            return {
                "dist_to_zone": DEFAULT_DIST_TO_ZONE,
                "dir_of_travel": DEFAULT_DIR_OF_TRAVEL,
                "nearest": DEFAULT_NEAREST,
            }

        entity_name = state_change_data.new_state.name
        devices_to_calculate = False
        devices_in_zone = []

        if (zone_state := self.hass.states.get(f"zone.{self.proximity_zone}")) is None:
            _LOGGER.error("Zone %s does not exists", self.proximity_zone)
            return {
                "dist_to_zone": DEFAULT_DIST_TO_ZONE,
                "dir_of_travel": DEFAULT_DIR_OF_TRAVEL,
                "nearest": DEFAULT_NEAREST,
            }

        proximity_latitude = zone_state.attributes.get(ATTR_LATITUDE)
        proximity_longitude = zone_state.attributes.get(ATTR_LONGITUDE)

        # Check for devices in the monitored zone.
        for device in self.proximity_devices:
            if (device_state := self.hass.states.get(device)) is None:
                devices_to_calculate = True
                continue

            if device_state.state not in self.ignored_zones:
                devices_to_calculate = True

            # Check the location of all devices.
            if (device_state.state).lower() == (self.proximity_zone).lower():
                device_friendly = device_state.name
                devices_in_zone.append(device_friendly)

        # No-one to track so reset the entity.
        if not devices_to_calculate:
            _LOGGER.debug("%s: no devices_to_calculate -> reset", self.friendly_name)
            return {
                "dist_to_zone": DEFAULT_DIST_TO_ZONE,
                "dir_of_travel": DEFAULT_DIR_OF_TRAVEL,
                "nearest": DEFAULT_NEAREST,
            }

        # At least one device is in the monitored zone so update the entity.
        if devices_in_zone:
            _LOGGER.debug(
                "%s: at least one device is in zone -> arrived", self.friendly_name
            )
            return {
                "dist_to_zone": 0,
                "dir_of_travel": "arrived",
                "nearest": ", ".join(devices_in_zone),
            }

        # We can't check proximity because latitude and longitude don't exist.
        if "latitude" not in state_change_data.new_state.attributes:
            _LOGGER.debug("%s: latitude and longitude -> reset", self.friendly_name)
            return self.data

        # Collect distances to the zone for all devices.
        distances_to_zone: dict[str, float] = {}
        for device in self.proximity_devices:
            # Ignore devices in an ignored zone.
            device_state = self.hass.states.get(device)
            if not device_state or device_state.state in self.ignored_zones:
                continue

            # Ignore devices if proximity cannot be calculated.
            if (
                ATTR_LATITUDE not in device_state.attributes
                or ATTR_LONGITUDE not in device_state.attributes
            ):
                continue

            # Calculate the distance to the proximity zone.
            proximity = distance(
                proximity_latitude,
                proximity_longitude,
                device_state.attributes[ATTR_LATITUDE],
                device_state.attributes[ATTR_LONGITUDE],
            )

            # Add the device and distance to a dictionary.
            assert proximity is not None  # there is no way that proximity could be None
            distances_to_zone[device] = round(
                DistanceConverter.convert(
                    proximity, UnitOfLength.METERS, self.unit_of_measurement
                ),
                1,
            )

        # Loop through each of the distances collected and work out the
        # closest.
        closest_device: str | None = None
        dist_to_zone: float | None = None

        for device, zone in distances_to_zone.items():
            if not dist_to_zone or zone < dist_to_zone:
                closest_device = device
                dist_to_zone = zone

        # If the closest device is one of the other devices.
        if closest_device is not None and closest_device != state_change_data.entity_id:
            _LOGGER.debug(
                "%s: closest device is one of the other devices -> unknown",
                self.friendly_name,
            )
            device_state = self.hass.states.get(closest_device)
            assert device_state
            return {
                "dist_to_zone": round(distances_to_zone[closest_device]),
                "dir_of_travel": "unknown",
                "nearest": device_state.name,
            }

        # Stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG).
        if (
            state_change_data.old_state is None
            or "latitude" not in state_change_data.old_state.attributes
        ):
            _LOGGER.debug(
                "%s: no lat and lon in old_state -> unknown", self.friendly_name
            )
            return {
                "dist_to_zone": round(distances_to_zone[state_change_data.entity_id]),
                "dir_of_travel": "unknown",
                "nearest": entity_name,
            }

        # Reset the variables
        distance_travelled: float = 0

        # Calculate the distance travelled.
        old_distance = distance(
            proximity_latitude,
            proximity_longitude,
            state_change_data.old_state.attributes[ATTR_LATITUDE],
            state_change_data.old_state.attributes[ATTR_LONGITUDE],
        )
        new_distance = distance(
            proximity_latitude,
            proximity_longitude,
            state_change_data.new_state.attributes[ATTR_LATITUDE],
            state_change_data.new_state.attributes[ATTR_LONGITUDE],
        )
        assert new_distance is not None and old_distance is not None
        distance_travelled = round(new_distance - old_distance, 1)

        # Check for tolerance
        if distance_travelled < self.tolerance * -1:
            direction_of_travel = "towards"
        elif distance_travelled > self.tolerance:
            direction_of_travel = "away_from"
        else:
            direction_of_travel = "stationary"

        # Update the proximity entity
        dist_to: float | str
        # at this point, it is ensured that dist_to_zone is valid
        assert dist_to_zone is not None
        dist_to = round(dist_to_zone)

        _LOGGER.debug(
            "%s updated: distance=%s: direction=%s: device=%s",
            self.friendly_name,
            dist_to,
            direction_of_travel,
            entity_name,
        )

        return {
            "dist_to_zone": dist_to,
            "dir_of_travel": direction_of_travel,
            "nearest": entity_name,
        }
