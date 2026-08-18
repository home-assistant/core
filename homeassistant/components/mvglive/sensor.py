"""Support for departure information for public transport in Munich."""

from copy import deepcopy
import logging
from typing import Any, override

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DESTINATIONS,
    CONF_ENABLE_MESSAGES,
    CONF_LINES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_STATION,
    CONF_TIMEOFFSET,
    DEFAULT_ENABLE_MESSAGES,
    DOMAIN,
)
from .coordinator import MvgConfigEntry, MvgDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_DEPARTURE = "nextdeparture"

NONE_ICON = "mdi:clock"

ATTRIBUTION = "Data provided by mvg.de"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STATION): cv.string,
                vol.Optional(CONF_DESTINATIONS, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_LINES, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_PRODUCTS, default=None): cv.ensure_list_csv,
                vol.Optional(CONF_TIMEOFFSET, default=0): cv.positive_int,
                vol.Optional(CONF_NUMBER, default=5): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
            }
        ]
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration as config entries."""
    for nextdeparture in config[CONF_NEXT_DEPARTURE]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=nextdeparture
            )
        )

    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version=None,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MvgConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MVG sensor from a config entry."""
    entities: list[SensorEntity] = [MVGSensor(entry)]
    if entry.options.get(CONF_ENABLE_MESSAGES, DEFAULT_ENABLE_MESSAGES):
        entities.append(MVGMessagesSensor(entry))
    async_add_entities(entities)


def _get_minutes_until_departure(departure_time: int) -> int:
    """Calculate the time difference in minutes between the current time and a given departure time.

    Args:
        departure_time: Unix timestamp of the departure time, in seconds.

    Returns:
        The time difference in minutes, as an integer.

    """
    current_time = dt_util.utcnow()
    departure_datetime = dt_util.utc_from_timestamp(departure_time)
    time_difference = (departure_datetime - current_time).total_seconds()
    return int(time_difference / 60.0)


def _filter_departures(
    departures: list[dict[str, Any]],
    destinations: list[str],
    lines: list[str],
    products: list[str] | None,
    timeoffset: int,
) -> list[dict[str, Any]]:
    """Filter and shape raw departures according to the entity's options."""
    filtered: list[dict[str, Any]] = []
    for departure in departures:
        if "" not in destinations[:1] and departure["destination"] not in destinations:
            continue

        if "" not in lines[:1] and departure["line"] not in lines:
            continue

        if products and departure["type"] not in products:
            continue

        time_to_departure = _get_minutes_until_departure(departure["time"])
        if time_to_departure < timeoffset:
            continue

        nextdep = {
            k: departure.get(k, "")
            for k in ("destination", "line", "type", "cancelled", "icon", "platform")
        }
        nextdep["time_in_mins"] = time_to_departure
        filtered.append(nextdep)

    return filtered


class MVGSensor(CoordinatorEntity[MvgDataUpdateCoordinator], SensorEntity):
    """Implementation of an MVG sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_has_entity_name = True

    def __init__(self, entry: MvgConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._departures: list[dict[str, Any]] = []

    def _update_from_coordinator_data(self) -> None:
        """Recompute filtered departures from the latest coordinator data."""
        options = self._entry.options
        self._departures = _filter_departures(
            self.coordinator.data.departures,
            options.get(CONF_DESTINATIONS, [""]),
            options.get(CONF_LINES, [""]),
            options.get(CONF_PRODUCTS),
            options.get(CONF_TIMEOFFSET, 0),
        )

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator_data()
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Compute the initial state once the entity is added."""
        await super().async_added_to_hass()
        self._update_from_coordinator_data()

    @property
    @override
    def native_value(self) -> int | None:
        """Return the next departure time."""
        if not self._departures:
            return None
        return self._departures[0].get("time_in_mins")

    @property
    @override
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        if not self._departures:
            return NONE_ICON
        return self._departures[0]["icon"]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self._departures:
            return None
        attr = dict(self._departures[0])  # next departure attributes
        attr["departures"] = deepcopy(self._departures)  # all departures dictionary
        return attr


class MVGMessagesSensor(CoordinatorEntity[MvgDataUpdateCoordinator], SensorEntity):
    """Sensor exposing MVG-wide incident messages (all lines and modes of transport).

    The MVG incident feed is network-wide, not specific to the station the
    owning config entry was set up for; the content is identical across all
    stations that have it enabled. It is still named and toggled per station
    (options flow) rather than as a single shared entity, since entities must
    belong to exactly one config entry in Home Assistant.
    """

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:alert-circle-outline"
    _attr_has_entity_name = True

    def __init__(self, entry: MvgConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_messages"
        self._attr_name = f"{entry.title} Messages"

    @property
    @override
    def native_value(self) -> int:
        """Return the number of active incident messages."""
        return len(self.coordinator.data.messages)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"messages": deepcopy(self.coordinator.data.messages)}
