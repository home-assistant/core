"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ROUTES, DOMAIN, INTEGRATION_TITLE, ROUTE_MODEL, ROUTES_SCHEMA
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator
from .utils import (
    get_actual_arrival_platform,
    get_actual_arrival_time_str,
    get_actual_departure_platform,
    get_actual_departure_time_str,
    get_arrival_delay,
    get_coordinator_data_attribute,
    get_departure_delay,
    get_departure_time_str,
    get_going,
    get_planned_arrival_platform,
    get_planned_arrival_time_str,
    get_planned_departure_platform,
    get_planned_departure_time_str,
    get_route,
    get_status,
    get_transfers,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Optional(CONF_ROUTES): ROUTES_SCHEMA}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor."""

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
            breaks_in_ha_version="2026.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the departure sensor from a config entry."""

    coordinators = config_entry.runtime_data

    for subentry_id, coordinator in coordinators.items():
        # Build entity from coordinator fields directly
        entity = NSDepartureSensor(
            subentry_id,
            coordinator,
        )

        # Add entity with proper subentry association
        async_add_entities([entity], config_subentry_id=subentry_id)


class NSDepartureSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Implementation of a NS Departure Sensor (legacy)."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"

    def __init__(
        self,
        subentry_id: str,
        coordinator: NSDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = coordinator.name
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{subentry_id}-actual_departure"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._subentry_id)},
            name=self._name,
            manufacturer=INTEGRATION_TITLE,
            model=ROUTE_MODEL,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        first_trip = get_coordinator_data_attribute(self.coordinator, "first_trip")
        return get_departure_time_str(first_trip)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        first_trip = get_coordinator_data_attribute(self.coordinator, "first_trip")
        next_trip = get_coordinator_data_attribute(self.coordinator, "next_trip")

        if not first_trip:
            return None

        route = get_route(first_trip)
        status = get_status(first_trip)

        # Static attributes
        return {
            "going": get_going(first_trip),
            "departure_time_planned": get_planned_departure_time_str(first_trip),
            "departure_time_actual": get_actual_departure_time_str(first_trip),
            "departure_delay": get_departure_delay(first_trip),
            "departure_platform_planned": get_planned_departure_platform(first_trip),
            "departure_platform_actual": get_actual_departure_platform(first_trip),
            "arrival_time_planned": get_planned_arrival_time_str(first_trip),
            "arrival_time_actual": get_actual_arrival_time_str(first_trip),
            "arrival_delay": get_arrival_delay(first_trip),
            "arrival_platform_planned": get_planned_arrival_platform(first_trip),
            "arrival_platform_actual": get_actual_arrival_platform(first_trip),
            "next": get_departure_time_str(next_trip) if next_trip else None,
            "status": status.lower() if status else None,
            "transfers": get_transfers(first_trip),
            "route": route,
            "remarks": None,
        }
