"""Support for HERE travel time sensors."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.here_travel_time import HERETravelTimeData
from homeassistant.components.here_travel_time.const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    ATTR_ROUTE,
    ATTR_TRAFFIC_MODE,
    ATTR_UNIT_SYSTEM,
    CONF_ARRIVAL,
    CONF_DEPARTURE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DEFAULT_NAME,
    DOMAIN,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_PUBLIC,
    ICON_TRUCK,
    ROUTE_MODE_FASTEST,
    ROUTE_MODES,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
    TRAVEL_MODES,
    TRAVEL_MODES_PUBLIC,
    UNITS,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_MODE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_ENTITY_ID = "destination_entity_id"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_ENTITY_ID = "origin_entity_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(
            CONF_DESTINATION_LATITUDE, "destination_coordinates"
        ): cv.latitude,
        vol.Inclusive(
            CONF_DESTINATION_LONGITUDE, "destination_coordinates"
        ): cv.longitude,
        vol.Exclusive(CONF_DESTINATION_LATITUDE, "destination"): cv.latitude,
        vol.Exclusive(CONF_DESTINATION_ENTITY_ID, "destination"): cv.entity_id,
        vol.Inclusive(CONF_ORIGIN_LATITUDE, "origin_coordinates"): cv.latitude,
        vol.Inclusive(CONF_ORIGIN_LONGITUDE, "origin_coordinates"): cv.longitude,
        vol.Exclusive(CONF_ORIGIN_LATITUDE, "origin"): cv.latitude,
        vol.Exclusive(CONF_ORIGIN_ENTITY_ID, "origin"): cv.entity_id,
        vol.Optional(CONF_DEPARTURE): cv.time,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=TRAVEL_MODE_CAR): vol.In(TRAVEL_MODES),
        vol.Optional(CONF_ROUTE_MODE, default=ROUTE_MODE_FASTEST): vol.In(ROUTE_MODES),
        vol.Optional(CONF_TRAFFIC_MODE, default=False): cv.boolean,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
        vol.Remove(CONF_SCAN_INTERVAL): cv.time_period,
    },
    extra=vol.REMOVE_EXTRA,
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_DESTINATION_LATITUDE, CONF_DESTINATION_ENTITY_ID),
    cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_ENTITY_ID),
    cv.key_value_schemas(
        CONF_MODE,
        {
            None: PLATFORM_SCHEMA,
            TRAVEL_MODE_BICYCLE: PLATFORM_SCHEMA,
            TRAVEL_MODE_CAR: PLATFORM_SCHEMA,
            TRAVEL_MODE_PEDESTRIAN: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC: PLATFORM_SCHEMA,
            TRAVEL_MODE_TRUCK: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC_TIME_TABLE: PLATFORM_SCHEMA.extend(
                {
                    vol.Exclusive(CONF_ARRIVAL, "arrival_departure"): cv.time,
                    vol.Exclusive(CONF_DEPARTURE, "arrival_departure"): cv.time,
                }
            ),
        },
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HERE travel time platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    _LOGGER.warning(
        "Your HERE travel time configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it will be "
        "removed in a future release"
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add HERE travel time entities from a config_entry."""

    async_add_entities(
        [HERETravelTimeSensor(hass.data[DOMAIN][config_entry.entry_id], config_entry)],
        True,
    )


class HERETravelTimeSensor(SensorEntity, CoordinatorEntity):
    """Representation of a HERE travel time sensor."""

    def __init__(
        self,
        here_data: HERETravelTimeData,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._config_entry = config_entry
        assert here_data.coordinator is not None
        super().__init__(here_data.coordinator)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            if (time := self.coordinator.data.get("traffic_time")) is not None:
                return str(round(time / 60))
        return None

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, None | float | str | bool] | None:
        """Return the state attributes."""
        if self.coordinator.data is not None:
            res = {
                ATTR_UNIT_SYSTEM: self.hass.config.units.name,
                ATTR_MODE: self._config_entry.data[CONF_MODE],
                ATTR_TRAFFIC_MODE: self._config_entry.options[CONF_TRAFFIC_MODE]
                == TRAFFIC_MODE_ENABLED,
                ATTR_DURATION: self.coordinator.data["base_time"] / 60,
                ATTR_DISTANCE: self.coordinator.data["distance"],
                ATTR_ROUTE: self.coordinator.data["route"],
                ATTR_DURATION_IN_TRAFFIC: self.coordinator.data["traffic_time"] / 60,
                ATTR_ORIGIN: self.coordinator.data["origin"],
                ATTR_DESTINATION: self.coordinator.data["destination"],
                ATTR_ORIGIN_NAME: self.coordinator.data["origin_name"],
                ATTR_DESTINATION_NAME: self.coordinator.data["destination_name"],
            }
            if (attribution := self.coordinator.data.get("attribution")) is not None:
                res[ATTR_ATTRIBUTION] = attribution
            return res
        return None

    @property
    def name(self) -> str:
        """Get the name of the sensor."""
        return str(self._config_entry.data[CONF_NAME])

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._config_entry.entry_id

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return TIME_MINUTES

    @property
    def icon(self) -> str:
        """Icon to use in the frontend depending on travel_mode."""
        travel_mode = self._config_entry.data[CONF_MODE]
        if travel_mode == TRAVEL_MODE_BICYCLE:
            return ICON_BICYCLE
        if travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if travel_mode in TRAVEL_MODES_PUBLIC:
            return ICON_PUBLIC
        if travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {
                (
                    DOMAIN,
                    f"{self._config_entry.data[CONF_ORIGIN]}_{self._config_entry.data[CONF_DESTINATION]}",
                )
            },
            "manufacturer": "HERE",
            "entry_type": "service",
        }
