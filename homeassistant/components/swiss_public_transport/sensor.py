"""Support for transport.opendata.ch."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from opendata_transport.exceptions import OpendataTransportError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    DateSelector,
    DurationSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACCESSIBILITY,
    CONF_BIKE,
    CONF_COUCHETTE,
    CONF_DATE,
    CONF_DESTINATION,
    CONF_DIRECT,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_OFFSET,
    CONF_PAGE,
    CONF_SLEEPER,
    CONF_START,
    CONF_TIME,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    DEFAULT_IS_ARRIVAL,
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    DOMAIN,
    MAX_LIMIT,
    MAX_PAGE,
    MIN_LIMIT,
    MIN_PAGE,
    SELECTOR_ACCESSIBILITY_TYPES,
    SELECTOR_TRANSPORTATION_TYPES,
)
from .helper import dict_duration_to_str_duration, offset_opendata

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)

ATTR_DEPARTURE_TIME1 = "next_departure"
ATTR_DEPARTURE_TIME2 = "next_on_departure"
ATTR_DEPARTURE_TIMES = "departures"
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
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_START): str,
        vol.Required(CONF_DESTINATION): str,
        vol.Optional(CONF_VIA): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_DATE): DateSelector(),
        vol.Optional(CONF_TIME): TimeSelector(),
        vol.Optional(CONF_OFFSET): DurationSelector(),
        vol.Optional(CONF_IS_ARRIVAL, default=DEFAULT_IS_ARRIVAL): bool,
        vol.Optional(CONF_LIMIT, default=DEFAULT_LIMIT): NumberSelector(
            NumberSelectorConfig(min=MIN_LIMIT, max=MAX_LIMIT)
        ),
        vol.Optional(CONF_PAGE, default=DEFAULT_PAGE): NumberSelector(
            NumberSelectorConfig(min=MIN_PAGE, max=MAX_PAGE)
        ),
        vol.Optional(
            CONF_TRANSPORTATIONS,
        ): SelectSelector(
            SelectSelectorConfig(
                options=SELECTOR_TRANSPORTATION_TYPES,
                multiple=True,
                translation_key="transportation",
            ),
        ),
        vol.Optional(
            CONF_ACCESSIBILITY,
        ): SelectSelector(
            SelectSelectorConfig(
                options=SELECTOR_ACCESSIBILITY_TYPES,
                multiple=True,
                translation_key="accessibility",
            ),
        ),
        vol.Optional(CONF_DIRECT): bool,
        vol.Optional(CONF_SLEEPER): bool,
        vol.Optional(CONF_COUCHETTE): bool,
        vol.Optional(CONF_BIKE): bool,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    opendata = hass.data[DOMAIN][config_entry.entry_id]

    start = config_entry.data[CONF_START]
    destination = config_entry.data[CONF_DESTINATION]
    name = config_entry.title
    limit = int(config_entry.data.get(CONF_LIMIT, None))
    date = config_entry.data.get(CONF_DATE, None)
    time = config_entry.data.get(CONF_TIME, None)
    offset = (
        dict_duration_to_str_duration(config_entry.data.get(CONF_OFFSET, None))
        if config_entry.data.get(CONF_OFFSET, None)
        else None
    )

    async_add_entities(
        [
            SwissPublicTransportSensor(
                opendata,
                start,
                destination,
                name,
                limit=limit,
                date=date,
                time=time,
                offset=offset,
            )
        ],
        update_before_add=True,
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

    def __init__(
        self,
        opendata,
        start,
        destination,
        name,
        limit,
        date,
        time,
        offset,
    ) -> None:
        """Initialize the sensor."""
        self._opendata = opendata
        self._name = name
        self._from = start
        self._to = destination
        self._limit = limit
        self._date = date
        self._time = time
        self._offset = offset

        self._remaining_time: timedelta | None = None

        self._connected = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return the available of the sensor."""
        return self._connected

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return (
            self._opendata.connections[0]["departure"]
            if self._opendata is not None and len(self._opendata.connections) > 0
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self._opendata is None or len(self._opendata.connections) == 0:
            return None

        departure_time = dt_util.parse_datetime(
            self._opendata.connections[0]["departure"]
        )
        self._remaining_time = (
            departure_time - dt_util.as_local(dt_util.utcnow())
            if departure_time
            else None
        )

        return {
            ATTR_TRAIN_NUMBER: self._opendata.connections[0]["number"],
            ATTR_PLATFORM: self._opendata.connections[0]["platform"],
            ATTR_TRANSFERS: self._opendata.connections[0]["transfers"],
            ATTR_DURATION: self._opendata.connections[0]["duration"],
            ATTR_DEPARTURE_TIME1: self._opendata.connections[1]["departure"]
            if self._limit is not None and self._limit > 1
            else None,
            ATTR_DEPARTURE_TIME2: self._opendata.connections[2]["departure"]
            if self._limit is not None and self._limit > 2
            else None,
            ATTR_DEPARTURE_TIMES: [
                c["departure"] for c in self._opendata.connections.values()
            ],
            ATTR_START: self._opendata.from_name,
            ATTR_TARGET: self._opendata.to_name,
            ATTR_REMAINING_TIME: f"{self._remaining_time}",
            ATTR_DELAY: self._opendata.connections[0]["delay"],
        }

    async def async_update(self) -> None:
        """Get the latest data from opendata.ch and update the states."""

        try:
            if not self._remaining_time or self._remaining_time.total_seconds() < 0:
                if self._offset and not self._date and not self._time:
                    offset_opendata(self._opendata, self._offset)

                await self._opendata.async_get_data()
        except OpendataTransportError:
            self._connected = False
            _LOGGER.warning(
                "Unable to connect and retrieve data from transport.opendata.ch"
            )
        else:
            if not self._connected:
                self._connected = True
                _LOGGER.info("Connection established with transport.opendata.ch")
