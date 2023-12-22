"""Support for transport.opendata.ch."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import OpendataTransportError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_DESTINATION, CONF_START, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)

ATTR_DEPARTURE_TIME1 = "next_departure"
ATTR_DEPARTURE_TIME2 = "next_on_departure"
ATTR_DURATION = "duration"
ATTR_PLATFORM = "platform"
ATTR_REMAINING_TIME = "remaining_time"
ATTR_START = "start"
ATTR_TARGET = "destination"
ATTR_TRAIN_NUMBER = "train_number"
ATTR_TRANSFERS = "transfers"
ATTR_DELAY = "delay"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_START): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    opendata = hass.data[DOMAIN][config_entry.entry_id]

    name = config_entry.title

    async_add_entities(
        [SwissPublicTransportSensor(opendata, name)],
        True,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Swiss public transport",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_${result['reason']}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_${result['reason']}",
        )


class SwissPublicTransportSensor(SensorEntity):
    """Implementation of an Swiss public transport sensor."""

    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_icon = "mdi:bus"

    def __init__(self, opendata: OpendataTransport, name: str) -> None:
        """Initialize the sensor."""
        self._opendata = opendata
        self._attr_name = name
        self._remaining_time: timedelta | None = None

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._opendata.connections[0]["departure"]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        departure_time = dt_util.parse_datetime(
            self._opendata.connections[0]["departure"]
        )
        if departure_time:
            remaining_time = departure_time - dt_util.as_local(dt_util.utcnow())
        else:
            remaining_time = None
        self._remaining_time = remaining_time

        return {
            ATTR_TRAIN_NUMBER: self._opendata.connections[0]["number"],
            ATTR_PLATFORM: self._opendata.connections[0]["platform"],
            ATTR_TRANSFERS: self._opendata.connections[0]["transfers"],
            ATTR_DURATION: self._opendata.connections[0]["duration"],
            ATTR_DEPARTURE_TIME1: self._opendata.connections[1]["departure"],
            ATTR_DEPARTURE_TIME2: self._opendata.connections[2]["departure"],
            ATTR_START: self._opendata.from_name,
            ATTR_TARGET: self._opendata.to_name,
            ATTR_REMAINING_TIME: f"{self._remaining_time}",
            ATTR_DELAY: self._opendata.connections[0]["delay"],
        }

    async def async_update(self) -> None:
        """Get the latest data from opendata.ch and update the states."""

        try:
            if not self._remaining_time or self._remaining_time.total_seconds() < 0:
                await self._opendata.async_get_data()
        except OpendataTransportError:
            self._attr_available = False
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
        else:
            if not self._attr_available:
                self._attr_available = True
                _LOGGER.info("Connection established with transport.opendata.ch")
