"""Support for departure information for public transport in Munich."""

from copy import deepcopy
from datetime import timedelta
import logging
from typing import Any, override

from mvg import MvgApi, MvgApiError, TransportType
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DESTINATIONS,
    CONF_DIRECTIONS,
    CONF_LINES,
    CONF_NUMBER,
    CONF_PRODUCTS,
    CONF_STATION,
    CONF_STATION_ID,
    CONF_TIMEOFFSET,
    DEFAULT_DESTINATIONS,
    DEFAULT_LINES,
    DEFAULT_NUMBER,
    DEFAULT_TIMEOFFSET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_NEXT_DEPARTURE = "nextdeparture"

NONE_ICON = "mdi:clock"

ATTRIBUTION = "Data provided by mvg.de"

SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STATION): cv.string,
                vol.Optional(CONF_DESTINATIONS, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_DIRECTIONS): cv.ensure_list_csv,
                vol.Optional(CONF_LINES, default=[""]): cv.ensure_list_csv,
                vol.Optional(CONF_PRODUCTS): cv.ensure_list_csv,
                vol.Optional(CONF_TIMEOFFSET, default=0): cv.positive_int,
                vol.Optional(CONF_NUMBER, default=1): cv.positive_int,
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
    stations = config[CONF_NEXT_DEPARTURE]
    results = [
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=nextdeparture
        )
        for nextdeparture in stations
    ]

    all_imported = True
    for nextdeparture, result in zip(stations, results, strict=True):
        if (
            result["type"] is FlowResultType.ABORT
            and result["reason"] != "already_configured"
        ):
            all_imported = False
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{result['reason']}_{nextdeparture[CONF_STATION]}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
                translation_placeholders={"station": nextdeparture[CONF_STATION]},
            )

    if all_imported:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2027.3.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MVG sensor from a config entry."""
    async_add_entities([MVGSensor(entry)], True)


def _get_minutes_until_departure(departure_time: int) -> int:
    """Calculate the time difference in minutes between the current time and a given departure time.

    Args:
        departure_time: Unix timestamp of the departure time, in seconds.

    Returns:
        The time difference in minutes, as an integer, rounded down so that
        already-departed connections stay negative instead of clamping to 0.

    """
    current_time = dt_util.utcnow()
    departure_datetime = dt_util.utc_from_timestamp(departure_time)
    time_difference = (departure_datetime - current_time).total_seconds()
    return int(time_difference // 60)


def _filter_departures(
    departures: list[dict[str, Any]],
    destinations: list[str],
    lines: list[str],
    timeoffset: int,
) -> list[dict[str, Any]]:
    """Filter and shape raw departures according to the entity's options."""
    filtered: list[dict[str, Any]] = []
    for departure in departures:
        if "" not in destinations[:1] and departure["destination"] not in destinations:
            continue

        if "" not in lines[:1] and departure["line"] not in lines:
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


class MVGSensor(SensorEntity):
    """Implementation of an MVG sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._station_id: str = entry.data[CONF_STATION_ID]
        options = entry.options
        self._destinations: list[str] = options.get(
            CONF_DESTINATIONS, DEFAULT_DESTINATIONS
        )
        self._lines: list[str] = options.get(CONF_LINES, DEFAULT_LINES)
        products: list[str] | None = options.get(CONF_PRODUCTS)
        self._transport_types = (
            [product for product in TransportType if product.value[0] in products]
            if products
            else None
        )
        self._timeoffset: int = options.get(CONF_TIMEOFFSET, DEFAULT_TIMEOFFSET)
        self._number: int = options.get(CONF_NUMBER, DEFAULT_NUMBER)
        self._attr_unique_id = entry.unique_id
        self._attr_name = entry.title
        self._departures: list[dict[str, Any]] = []

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        try:
            departures = await MvgApi.departures_async(
                station_id=self._station_id,
                limit=self._number,
                offset=self._timeoffset,
                transport_types=self._transport_types,
            )
        except MvgApiError as err:
            _LOGGER.warning("Could not update MVG departures: %s", err)
            self._departures = []
            return

        self._departures = _filter_departures(
            departures,
            self._destinations,
            self._lines,
            self._timeoffset,
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the next departure time."""
        if not self._departures:
            return None
        return int(self._departures[0]["time_in_mins"])

    @property
    @override
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        if not self._departures:
            return NONE_ICON
        return str(self._departures[0]["icon"]) or NONE_ICON

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self._departures:
            return None
        attr = dict(self._departures[0])  # next departure attributes
        attr["departures"] = deepcopy(self._departures)  # all departures dictionary
        return attr
