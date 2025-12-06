"""Real-time information about public transport departures in Norway."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, UnitOfTime
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

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
    ATTRIBUTION,
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_ICON,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
    ICONS,
)
from .coordinator import EnturConfigEntry, EnturCoordinator

_LOGGER = logging.getLogger(__name__)

# Legacy YAML platform schema for import
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_IDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_EXPAND_PLATFORMS, default=True): cv.boolean,
        vol.Optional(CONF_NAME, default="Entur"): cv.string,
        vol.Optional("show_on_map", default=False): cv.boolean,
        vol.Optional(CONF_WHITELIST_LINES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_OMIT_NON_BOARDING, default=True): cv.boolean,
        vol.Optional(
            CONF_NUMBER_OF_DEPARTURES, default=DEFAULT_NUMBER_OF_DEPARTURES
        ): vol.All(cv.positive_int, vol.Range(min=2, max=10)),
    }
)


def _due_in_minutes(timestamp: datetime | None) -> int | None:
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
    """Set up the Entur public transport sensor from YAML configuration.

    This triggers an import flow to migrate the YAML configuration to a config entry.
    """
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
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2027.1.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Entur public transport",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.1.0",
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
    coordinator = entry.runtime_data

    entities = [
        EnturSensor(coordinator, stop_id)
        for stop_id in coordinator.data
    ]
    async_add_entities(entities)


class EnturSensor(CoordinatorEntity[EnturCoordinator], SensorEntity):
    """Sensor representing a public transport stop/quay."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: EnturCoordinator,
        stop_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_id = stop_id

        # Get stop name for the entity
        stop_info = coordinator.data.get(stop_id)
        stop_name = stop_info.name if stop_info else stop_id

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{stop_id}"
        self._attr_name = stop_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Entur",
            manufacturer="Entur",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://entur.no/",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._stop_id in self.coordinator.data

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor (minutes until next departure)."""
        stop_info = self.coordinator.data.get(self._stop_id)
        if stop_info is None:
            return None

        calls = stop_info.estimated_calls
        if not calls:
            return None

        return _due_in_minutes(calls[0].expected_departure_time)

    @property
    def icon(self) -> str:
        """Return the icon based on transport mode."""
        stop_info = self.coordinator.data.get(self._stop_id)
        if stop_info is None:
            return DEFAULT_ICON

        calls = stop_info.estimated_calls
        if not calls:
            return DEFAULT_ICON

        return ICONS.get(calls[0].transport_mode, DEFAULT_ICON)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {ATTR_STOP_ID: self._stop_id}

        stop_info = self.coordinator.data.get(self._stop_id)
        if stop_info is None:
            return attrs

        # Add location if configured
        if (
            self.coordinator.show_on_map
            and stop_info.latitude
            and stop_info.longitude
        ):
            attrs[CONF_LATITUDE] = stop_info.latitude
            attrs[CONF_LONGITUDE] = stop_info.longitude

        calls = stop_info.estimated_calls
        if not calls:
            return attrs

        # First departure
        first_call = calls[0]
        attrs[ATTR_ROUTE] = first_call.front_display
        attrs[ATTR_ROUTE_ID] = first_call.line_id
        attrs[ATTR_EXPECTED_AT] = first_call.expected_departure_time.strftime("%H:%M")
        attrs[ATTR_REALTIME] = first_call.is_realtime
        attrs[ATTR_DELAY] = first_call.delay_in_min

        # Second departure (next up)
        if len(calls) >= 2:
            second_call = calls[1]
            attrs[ATTR_NEXT_UP_ROUTE] = second_call.front_display
            attrs[ATTR_NEXT_UP_ROUTE_ID] = second_call.line_id
            attrs[ATTR_NEXT_UP_AT] = second_call.expected_departure_time.strftime(
                "%H:%M"
            )
            attrs[ATTR_NEXT_UP_IN] = (
                f"{_due_in_minutes(second_call.expected_departure_time)} min"
            )
            attrs[ATTR_NEXT_UP_REALTIME] = second_call.is_realtime
            attrs[ATTR_NEXT_UP_DELAY] = second_call.delay_in_min

        # Additional departures
        if len(calls) >= 3:
            for i, call in enumerate(calls[2:], start=3):
                prefix = "" if call.is_realtime else "ca. "
                attrs[f"departure_#{i}"] = (
                    f"{prefix}{call.expected_departure_time.strftime('%H:%M')} "
                    f"{call.front_display}"
                )

        return attrs

