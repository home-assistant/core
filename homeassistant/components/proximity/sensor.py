"""Support for Proximity sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_DEVICES,
    CONF_NAME,
    CONF_ZONE,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from homeassistant.util.location import distance

from .const import (
    ATTR_DIR_OF_TRAVEL,
    ATTR_DIST_FROM,
    ATTR_NEAREST,
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    DEFAULT_DIR_OF_TRAVEL,
    DEFAULT_NEAREST,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_DIST_FROM,
        translation_key=ATTR_DIST_FROM,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
    ),
    SensorEntityDescription(
        key=ATTR_DIR_OF_TRAVEL,
        translation_key=ATTR_DIR_OF_TRAVEL,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key=ATTR_NEAREST, translation_key=ATTR_NEAREST, icon="mdi:near-me"
    ),
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Proximity sensor platform."""
    if discovery_info is None:
        return

    async_add_entities(
        ProximitySensor(sensor, dict(discovery_info)) for sensor in SENSORS
    )


class ProximitySensor(SensorEntity):
    """Represents a Proximity sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, description: SensorEntityDescription, config: dict) -> None:
        """Initialize the proximity."""
        self.ignored_zones = config[CONF_IGNORED_ZONES]
        self.proximity_devices = config[CONF_DEVICES]
        self.tolerance = config[CONF_TOLERANCE]
        self.proximity_zone = f"zone.{config[CONF_ZONE]}"
        self.config_name = slugify(config[CONF_NAME])

        self.data: dict[str, int | str | None] = {
            ATTR_DIST_FROM: None,
            ATTR_DIR_OF_TRAVEL: slugify(DEFAULT_DIR_OF_TRAVEL),
            ATTR_NEAREST: DEFAULT_NEAREST,
        }

        self.entity_description = description

        self._attr_unique_id = slugify(f"{DOMAIN}_{self.config_name}_{description.key}")

    @property
    def native_value(self) -> int | str | None:
        """Return native sensor value."""
        return self.data[self.entity_description.key]

    async def async_added_to_hass(self) -> None:
        """Start listening for state changes."""
        self.async_on_remove(
            async_track_state_change(
                self.hass,
                self.proximity_devices,
                self.async_check_proximity_state_change,
            )
        )

    @callback
    def async_check_proximity_state_change(
        self, entity: str, old_state: State | None, new_state: State | None
    ) -> None:
        """Perform the proximity checking."""
        if new_state is None:
            return

        entity_name = new_state.name
        devices_to_calculate = False
        devices_in_zone = ""

        zone_state = self.hass.states.get(self.proximity_zone)
        proximity_latitude = (
            zone_state.attributes.get(ATTR_LATITUDE) if zone_state else None
        )
        proximity_longitude = (
            zone_state.attributes.get(ATTR_LONGITUDE) if zone_state else None
        )

        # Check for devices in the monitored zone.
        for device in self.proximity_devices:
            if (device_state := self.hass.states.get(device)) is None:
                devices_to_calculate = True
                continue

            if device_state.state not in self.ignored_zones:
                devices_to_calculate = True

            # Check the location of all devices.
            if (device_state.state).lower() == (self.config_name).lower():
                device_friendly = device_state.name
                if devices_in_zone != "":
                    devices_in_zone = f"{devices_in_zone}, "
                devices_in_zone = devices_in_zone + device_friendly

        # No-one to track so reset the entity.
        if not devices_to_calculate:
            self.data[ATTR_DIST_FROM] = None
            self.data[ATTR_DIR_OF_TRAVEL] = slugify(DEFAULT_DIR_OF_TRAVEL)
            self.data[ATTR_NEAREST] = DEFAULT_NEAREST
            self.async_write_ha_state()
            return

        # At least one device is in the monitored zone so update the entity.
        if devices_in_zone != "":
            self.data[ATTR_DIST_FROM] = 0
            self.data[ATTR_DIR_OF_TRAVEL] = "arrived"
            self.data[ATTR_NEAREST] = devices_in_zone
            self.async_write_ha_state()
            return

        # We can't check proximity because latitude and longitude don't exist.
        if "latitude" not in new_state.attributes:
            return

        # Collect distances to the zone for all devices.
        distances_to_zone: dict[str, int] = {}
        for device in self.proximity_devices:
            # Ignore devices in an ignored zone.
            device_state = self.hass.states.get(device)
            if not device_state or device_state.state in self.ignored_zones:
                continue

            # Ignore devices if proximity cannot be calculated.
            if "latitude" not in device_state.attributes:
                continue

            # Calculate the distance to the proximity zone.
            proximity = distance(
                proximity_latitude,
                proximity_longitude,
                device_state.attributes[ATTR_LATITUDE],
                device_state.attributes[ATTR_LONGITUDE],
            )

            # Add the device and distance to a dictionary.
            if not proximity:
                continue
            distances_to_zone[device] = round(proximity)

        # Loop through each of the distances collected and work out the
        # closest.
        closest_device: str | None = None
        dist_to_zone: int | None = None

        for device, zone in distances_to_zone.items():
            if not dist_to_zone or zone < dist_to_zone:
                closest_device = device
                dist_to_zone = zone

        # If the closest device is one of the other devices.
        if closest_device is not None and closest_device != entity:
            self.data[ATTR_DIST_FROM] = round(distances_to_zone[closest_device])
            self.data[ATTR_DIR_OF_TRAVEL] = "unknown"
            device_state = self.hass.states.get(closest_device)
            assert device_state
            self.data[ATTR_NEAREST] = device_state.name
            self.async_write_ha_state()
            return

        # Stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG).
        if old_state is None or "latitude" not in old_state.attributes:
            self.data[ATTR_DIST_FROM] = round(distances_to_zone[entity])
            self.data[ATTR_DIR_OF_TRAVEL] = "unknown"
            self.data[ATTR_NEAREST] = entity_name
            self.async_write_ha_state()
            return

        # Reset the variables
        distance_travelled: float = 0

        # Calculate the distance travelled.
        old_distance = distance(
            proximity_latitude,
            proximity_longitude,
            old_state.attributes[ATTR_LATITUDE],
            old_state.attributes[ATTR_LONGITUDE],
        )
        new_distance = distance(
            proximity_latitude,
            proximity_longitude,
            new_state.attributes[ATTR_LATITUDE],
            new_state.attributes[ATTR_LONGITUDE],
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
        self.data[ATTR_DIST_FROM] = dist_to_zone
        self.data[ATTR_DIR_OF_TRAVEL] = direction_of_travel
        self.data[ATTR_NEAREST] = entity_name
        self.async_write_ha_state()
        _LOGGER.debug(
            "proximity.%s update entity: distance=%s: direction=%s: device=%s",
            self.name,
            dist_to_zone,
            direction_of_travel,
            entity_name,
        )

        _LOGGER.info("%s: proximity calculation complete", entity_name)
