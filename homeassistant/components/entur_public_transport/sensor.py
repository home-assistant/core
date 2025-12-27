"""Real-time information about public transport departures in Norway."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from enturclient import EnturPublicTransportData
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SHOW_ON_MAP,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util

from .const import (
    ATTR_DELAY,
    ATTR_EXPECTED_AT,
    ATTR_NEXT_UP_AT,
    ATTR_NEXT_UP_DELAY,
    ATTR_NEXT_UP_IN,
    ATTR_NEXT_UP_REALTIME,
    ATTR_NEXT_UP_ROUTE,
    ATTR_NEXT_UP_ROUTE_ID,
    ATTR_REALTIME,
    ATTR_ROUTE,
    ATTR_ROUTE_ID,
    ATTR_STOP_ID,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_ICON_KEY,
    DEFAULT_NAME,
    DOMAIN,
    ICONS,
)

if TYPE_CHECKING:
    from . import EnturConfigEntry

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
        vol.Optional(CONF_WHITELIST_LINES, default=[]): cv.ensure_list,
        vol.Optional(CONF_OMIT_NON_BOARDING, default=True): cv.boolean,
        vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=2): vol.All(
            cv.positive_int, vol.Range(min=2, max=10)
        ),
    }
)


def due_in_minutes(timestamp: datetime) -> int:
    """Get the time in minutes from a timestamp."""
    if timestamp is None:
        return None
    diff = timestamp - dt_util.now()
    return int(diff.total_seconds() / 60)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Entur public transport sensor."""
    # Trigger the import flow to migrate YAML to config entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue",
            breaks_in_ha_version="2026.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Entur public transport",
                "error_reason": result.get("reason", "unknown"),
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Entur public transport",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnturConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Entur sensors from a config entry."""
    data = entry.runtime_data.data
    proxy = entry.runtime_data.proxy
    show_on_map = entry.runtime_data.show_on_map
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    entities = []
    for place in data.all_stop_places_quays():
        try:
            given_name = f"{name} {data.get_stop_info(place).name}"
        except KeyError:
            given_name = f"{name} {place}"

        entities.append(
            EnturPublicTransportSensor(proxy, given_name, place, show_on_map)
        )

    async_add_entities(entities, True)


class EnturProxy:
    """Proxy for the Entur client.

    Ensure throttle to not hit rate limiting on the API.
    """

    def __init__(self, api):
        """Initialize the proxy."""
        self._api = api

    @Throttle(timedelta(seconds=15))
    async def async_update(self) -> None:
        """Update data in client."""
        await self._api.update()

    def get_stop_info(self, stop_id: str) -> dict:
        """Get info about specific stop place."""
        return self._api.get_stop_info(stop_id)


class EnturPublicTransportSensor(SensorEntity):
    """Implementation of a Entur public transport sensor."""

    _attr_attribution = "Data provided by entur.org under NLOD"

    def __init__(
        self, api: EnturProxy, name: str, stop: str, show_on_map: bool
    ) -> None:
        """Initialize the sensor."""
        self.api = api
        self._stop = stop
        self._show_on_map = show_on_map
        self._name = name
        self._state: int | None = None
        self._icon = ICONS[DEFAULT_ICON_KEY]
        self._attributes: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        self._attributes[ATTR_STOP_ID] = self._stop
        return self._attributes

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return self._icon

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        await self.api.async_update()

        self._attributes = {}

        data: EnturPublicTransportData = self.api.get_stop_info(self._stop)
        if data is None:
            self._state = None
            return

        if self._show_on_map and data.latitude and data.longitude:
            self._attributes[CONF_LATITUDE] = data.latitude
            self._attributes[CONF_LONGITUDE] = data.longitude

        if not (calls := data.estimated_calls):
            self._state = None
            return

        self._state = due_in_minutes(calls[0].expected_departure_time)
        self._icon = ICONS.get(calls[0].transport_mode, ICONS[DEFAULT_ICON_KEY])

        self._attributes[ATTR_ROUTE] = calls[0].front_display
        self._attributes[ATTR_ROUTE_ID] = calls[0].line_id
        self._attributes[ATTR_EXPECTED_AT] = calls[0].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[ATTR_REALTIME] = calls[0].is_realtime
        self._attributes[ATTR_DELAY] = calls[0].delay_in_min

        number_of_calls = len(calls)
        if number_of_calls < 2:
            return

        self._attributes[ATTR_NEXT_UP_ROUTE] = calls[1].front_display
        self._attributes[ATTR_NEXT_UP_ROUTE_ID] = calls[1].line_id
        self._attributes[ATTR_NEXT_UP_AT] = calls[1].expected_departure_time.strftime(
            "%H:%M"
        )
        self._attributes[ATTR_NEXT_UP_IN] = (
            f"{due_in_minutes(calls[1].expected_departure_time)} min"
        )
        self._attributes[ATTR_NEXT_UP_REALTIME] = calls[1].is_realtime
        self._attributes[ATTR_NEXT_UP_DELAY] = calls[1].delay_in_min

        if number_of_calls < 3:
            return

        for i, call in enumerate(calls[2:]):
            key_name = f"departure_#{i + 3}"
            self._attributes[key_name] = (
                f"{'' if bool(call.is_realtime) else 'ca. '}"
                f"{call.expected_departure_time.strftime('%H:%M')} {call.front_display}"
            )
