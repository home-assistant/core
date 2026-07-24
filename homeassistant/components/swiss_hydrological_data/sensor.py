"""Support for hydrological data from the Fed. Office for the Environment."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from requests.exceptions import RequestException
from swisshydrodata import SwissHydroData
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .const import CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_MAX_24H = "max-24h"
ATTR_MEAN_24H = "mean-24h"
ATTR_MIN_24H = "min-24h"
ATTR_STATION = "station"
ATTR_STATION_UPDATE = "station_update"
ATTR_WATER_BODY = "water_body"
ATTR_WATER_BODY_TYPE = "water_body_type"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SENSOR_DISCHARGE = "discharge"
SENSOR_LEVEL = "level"
SENSOR_TEMPERATURE = "temperature"

CONDITIONS = {
    SENSOR_DISCHARGE: "mdi:waves",
    SENSOR_LEVEL: "mdi:zodiac-aquarius",
    SENSOR_TEMPERATURE: "mdi:oil-temperature",
}

CONDITION_DETAILS = [
    ATTR_MAX_24H,
    ATTR_MEAN_24H,
    ATTR_MIN_24H,
]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION): vol.Coerce(int),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[SENSOR_TEMPERATURE]): vol.All(
            cv.ensure_list, [vol.In(CONDITIONS)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Swiss Hydrological Data configuration from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Swiss Hydrological Data",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.11.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Swiss Hydrological Data",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Swiss Hydrological Data sensors from a config entry."""
    hydro_data: HydrologicalData = entry.runtime_data
    station_id: int = entry.data[CONF_STATION]

    if hydro_data.data is None:
        return

    async_add_entities(
        SwissHydrologicalDataSensor(hydro_data, station_id, condition)
        for condition in CONDITIONS
        if condition in hydro_data.data.get("parameters", {})
    )


class HydrologicalData:
    """The Class for handling the data retrieval."""

    def __init__(self, station: int) -> None:
        """Initialize the data object."""
        self.station = station
        self.data: dict[str, Any] | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data."""
        try:
            self.data = SwissHydroData().get_station(self.station)
        except RequestException:
            _LOGGER.exception("Error retrieving data for station %s", self.station)
            self.data = None


class SwissHydrologicalDataSensor(SensorEntity):
    """Implementation of a Swiss hydrological sensor."""

    _attr_attribution = (
        "Data provided by the Swiss Federal Office for the Environment FOEN"
    )

    def __init__(
        self, hydro_data: HydrologicalData, station: int, condition: str
    ) -> None:
        """Initialize the Swiss hydrological sensor."""
        self.hydro_data = hydro_data
        data = hydro_data.data
        if TYPE_CHECKING:
            assert data is not None

        self._condition = condition
        self._data: dict[str, Any] | None = data
        self._attr_icon = CONDITIONS[condition]
        self._attr_name = f"{data['water-body-name']} {condition}"
        self._attr_native_unit_of_measurement = data["parameters"][condition]["unit"]
        self._attr_unique_id = f"{station}_{condition}"
        self._station = station
        value = data["parameters"][condition]["value"]
        self._attr_native_value = (
            round(value, 2) if isinstance(value, (int, float)) else None
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attrs: dict[str, Any] = {}

        if not self._data:
            return attrs

        attrs[ATTR_WATER_BODY_TYPE] = self._data["water-body-type"]
        attrs[ATTR_STATION] = self._data["name"]
        attrs[ATTR_STATION_UPDATE] = self._data["parameters"][self._condition][
            "datetime"
        ]

        for entry in CONDITION_DETAILS:
            attrs[entry.replace("-", "_")] = self._data["parameters"][self._condition][
                entry
            ]

        return attrs

    def update(self) -> None:
        """Get the latest data and update the state."""
        self.hydro_data.update()
        self._data = self.hydro_data.data

        self._attr_native_value = None
        if self._data is not None:
            state = self._data["parameters"][self._condition]["value"]
            if isinstance(state, (int, float)):
                self._attr_native_value = round(state, 2)
