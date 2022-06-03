"""Support for HERE travel time sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_MODE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HereTravelTimeDataUpdateCoordinator
from .const import (
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_TRAFFIC_MODE,
    ATTR_UNIT_SYSTEM,
    CONF_ARRIVAL,
    CONF_DEPARTURE,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
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

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(minutes=5)

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
    }
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
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
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
        [
            HERETravelTimeSensor(
                config_entry.entry_id,
                config_entry.data[CONF_NAME],
                config_entry.options[CONF_TRAFFIC_MODE],
                hass.data[DOMAIN][config_entry.entry_id],
            )
        ],
    )


class HERETravelTimeSensor(SensorEntity, CoordinatorEntity):
    """Representation of a HERE travel time sensor."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        traffic_mode: str,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._traffic_mode = traffic_mode == TRAFFIC_MODE_ENABLED
        self._attr_native_unit_of_measurement = TIME_MINUTES
        self._attr_name = name
        self._attr_unique_id = unique_id_prefix
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id_prefix)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
            manufacturer="HERE Technologies",
        )

    async def async_added_to_hass(self) -> None:
        """Wait for start so origin and destination entities can be resolved."""
        await super().async_added_to_hass()

        async def _update_at_start(_):
            await self.async_update()

        self.async_on_remove(async_at_start(self.hass, _update_at_start))

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            return str(
                round(
                    self.coordinator.data.get(
                        ATTR_DURATION_IN_TRAFFIC
                        if self._traffic_mode
                        else ATTR_DURATION
                    )
                )
            )
        return None

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, None | float | str | bool] | None:
        """Return the state attributes."""
        if self.coordinator.data is not None:
            res = {
                ATTR_UNIT_SYSTEM: self.coordinator.config.units,
                ATTR_MODE: self.coordinator.config.travel_mode,
                ATTR_TRAFFIC_MODE: self._traffic_mode,
                **self.coordinator.data,
            }
            res.pop(ATTR_ATTRIBUTION)
            return res
        return None

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get(ATTR_ATTRIBUTION)
        return None

    @property
    def icon(self) -> str:
        """Icon to use in the frontend depending on travel_mode."""
        if self.coordinator.config.travel_mode == TRAVEL_MODE_BICYCLE:
            return ICON_BICYCLE
        if self.coordinator.config.travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if self.coordinator.config.travel_mode in TRAVEL_MODES_PUBLIC:
            return ICON_PUBLIC
        if self.coordinator.config.travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR
