"""Support for the NOAA Tides and Currents API."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import noaa_coops as coops
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE, CONF_UNIT_SYSTEM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NoaaTidesConfigEntry
from .const import (
    CONF_STATION_ID,
    DEFAULT_TIMEZONE,
    DOMAIN,
    NAME,
    TIMEZONES,
    UNIT_SYSTEMS,
)
from .helpers import get_default_unit_system, get_station_unique_id

if TYPE_CHECKING:
    from pandas import Timestamp

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NOAA Tides"

SCAN_INTERVAL = timedelta(minutes=60)

DEPRECATE_YAML_IN_HA_VERSION = "2025.10.0"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIME_ZONE, default=DEFAULT_TIMEZONE): vol.In(TIMEZONES),
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNIT_SYSTEMS),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NOAA Tides and Currents sensor."""

    _LOGGER.debug("Importing from configuration.yaml: %s", config)

    station_id = config[CONF_STATION_ID]
    timezone = config.get(CONF_TIME_ZONE, DEFAULT_TIMEZONE)
    unit_system = config.get(CONF_UNIT_SYSTEM, get_default_unit_system(hass))

    user_data = {
        CONF_STATION_ID: station_id,
        CONF_TIME_ZONE: timezone,
        CONF_UNIT_SYSTEM: unit_system,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=user_data,
    )

    if result["type"] is FlowResultType.CREATE_ENTRY or (
        result["type"] is FlowResultType.ABORT
        and result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version=DEPRECATE_YAML_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": NAME,
            },
        )
        return

    if (
        result["type"] is FlowResultType.FORM
        and result["errors"] is not None
        and result["errors"]["base"] is not None
    ):
        _LOGGER.error(
            "Cannot import %s from configuration.yaml (station_id = %s): %s",
            DOMAIN,
            station_id,
            result["errors"]["base"],
        )
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['errors']['base']}",
            breaks_in_ha_version=DEPRECATE_YAML_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['errors']['base']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": NAME,
            },
        )
        return

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_import_issue_unknown",
        breaks_in_ha_version="2025.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_issue_unknown",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": NAME,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoaaTidesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add NOAA Tides sensor entry."""

    data = entry.runtime_data

    device_id = get_station_unique_id(data.station_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=data.name,
        entry_type=DeviceEntryType.SERVICE,
    )

    summary_sensor = NOAATidesAndCurrentsSensor(
        name=data.name,
        station_id=data.station_id,
        timezone=data.timezone,
        unit_system=data.unit_system,
        station=data.station,
        device_info=device_info,
    )

    async_add_entities([summary_sensor], True)


class NOAATidesData(TypedDict):
    """Representation of a single tide."""

    time_stamp: list[Timestamp]
    hi_lo: list[Literal["L", "H"]]
    predicted_wl: list[float]


class NOAATidesAndCurrentsSensor(SensorEntity):
    """Representation of a NOAA Tides and Currents sensor."""

    _attr_attribution = "Data provided by NOAA"

    def __init__(
        self,
        name: str | None,
        station_id: str,
        timezone: str | None,
        unit_system: str,
        station: coops.Station,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._name = name if name is not None else DEFAULT_NAME
        self._station_id = station_id
        self._timezone = timezone if timezone is not None else DEFAULT_TIMEZONE
        self._unit_system = unit_system
        self._station = station
        self.data: NOAATidesData | None = None
        self._attr_unique_id = f"{get_station_unique_id(station_id)}_summary"
        self._attr_device_info = device_info

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this device."""
        attr: dict[str, Any] = {}
        if self.data is None:
            return attr
        if self.data["hi_lo"][1] == "H":
            attr["high_tide_time"] = self.data["time_stamp"][1].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["high_tide_height"] = self.data["predicted_wl"][1]
            attr["low_tide_time"] = self.data["time_stamp"][2].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["low_tide_height"] = self.data["predicted_wl"][2]
        elif self.data["hi_lo"][1] == "L":
            attr["low_tide_time"] = self.data["time_stamp"][1].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["low_tide_height"] = self.data["predicted_wl"][1]
            attr["high_tide_time"] = self.data["time_stamp"][2].strftime(
                "%Y-%m-%dT%H:%M"
            )
            attr["high_tide_height"] = self.data["predicted_wl"][2]
        return attr

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.data is None:
            return None
        api_time = self.data["time_stamp"][0]
        if self.data["hi_lo"][0] == "H":
            tidetime = api_time.strftime("%-I:%M %p")
            return f"High tide at {tidetime}"
        if self.data["hi_lo"][0] == "L":
            tidetime = api_time.strftime("%-I:%M %p")
            return f"Low tide at {tidetime}"
        return None

    def update(self) -> None:
        """Get the latest data from NOAA Tides and Currents API."""
        begin = datetime.now()
        delta = timedelta(days=2)
        end = begin + delta
        try:
            df_predictions = self._station.get_data(
                begin_date=begin.strftime("%Y%m%d %H:%M"),
                end_date=end.strftime("%Y%m%d %H:%M"),
                product="predictions",
                datum="MLLW",
                interval="hilo",
                units=self._unit_system,
                time_zone=self._timezone,
            )
            api_data = df_predictions.head()
            self.data = NOAATidesData(
                time_stamp=list(api_data.index),
                hi_lo=list(api_data["type"].values),
                predicted_wl=list(api_data["v"].values),
            )
            _LOGGER.debug("Data = %s", api_data)
            _LOGGER.debug(
                "Recent Tide data queried with start time set to %s",
                begin.strftime("%m-%d-%Y %H:%M"),
            )
        except ValueError as err:
            _LOGGER.error("Check %s and Currents: %s", NAME, err.args)
            self.data = None
