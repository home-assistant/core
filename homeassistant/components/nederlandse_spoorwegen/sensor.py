"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY, CONF_NAME
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
from homeassistant.util.dt import parse_time

from .const import (
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    INTEGRATION_TITLE,
    ROUTE_MODEL,
)
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_VIA): cv.string,
        vol.Optional(CONF_TIME): cv.time,
    }
)

ROUTES_SCHEMA = vol.All(cv.ensure_list, [ROUTE_SCHEMA])

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
    """Implementation of a NS Departure Sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
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
        self._departure = coordinator.departure
        self._via = coordinator.via
        self._heading = coordinator.destination
        self._time = (
            parse_time(coordinator.departure_time)
            if coordinator.departure_time
            else None
        )
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
    def native_value(self) -> datetime | None:
        """Return the native value of the sensor."""
        route_data = self.coordinator.data
        if not route_data.first_trip:
            return None

        first_trip = route_data.first_trip
        if first_trip.departure_time_actual:
            return first_trip.departure_time_actual
        return first_trip.departure_time_planned

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        route_data = self.coordinator.data
        if not route_data:
            return None

        first_trip = route_data.first_trip
        next_trip = route_data.next_trip

        if not first_trip:
            return None

        route = []
        if first_trip.trip_parts:
            route = [first_trip.departure]
            route.extend(k.destination for k in first_trip.trip_parts)

        # Static attributes
        attributes = {
            "going": first_trip.going,
            "departure_time_planned": None,
            "departure_time_actual": None,
            "departure_delay": False,
            "departure_platform_planned": first_trip.departure_platform_planned,
            "departure_platform_actual": first_trip.departure_platform_actual,
            "arrival_time_planned": None,
            "arrival_time_actual": None,
            "arrival_delay": False,
            "arrival_platform_planned": first_trip.arrival_platform_planned,
            "arrival_platform_actual": first_trip.arrival_platform_actual,
            "next": None,
            "status": first_trip.status.lower() if first_trip.status else None,
            "transfers": first_trip.nr_transfers,
            "route": route,
            "remarks": None,
        }

        # Planned departure attributes
        if first_trip.departure_time_planned is not None:
            attributes["departure_time_planned"] = (
                first_trip.departure_time_planned.strftime("%H:%M")
            )

        # Actual departure attributes
        if first_trip.departure_time_actual is not None:
            attributes["departure_time_actual"] = (
                first_trip.departure_time_actual.strftime("%H:%M")
            )

        # Delay departure attributes
        if (
            attributes["departure_time_planned"]
            and attributes["departure_time_actual"]
            and attributes["departure_time_planned"]
            != attributes["departure_time_actual"]
        ):
            attributes["departure_delay"] = True

        # Planned arrival attributes
        if first_trip.arrival_time_planned is not None:
            attributes["arrival_time_planned"] = (
                first_trip.arrival_time_planned.strftime("%H:%M")
            )

        # Actual arrival attributes
        if first_trip.arrival_time_actual is not None:
            attributes["arrival_time_actual"] = first_trip.arrival_time_actual.strftime(
                "%H:%M"
            )

        # Delay arrival attributes
        if (
            attributes["arrival_time_planned"]
            and attributes["arrival_time_actual"]
            and attributes["arrival_time_planned"] != attributes["arrival_time_actual"]
        ):
            attributes["arrival_delay"] = True

        # Next trip attributes
        if next_trip:
            if next_trip.departure_time_actual is not None:
                attributes["next"] = next_trip.departure_time_actual.strftime("%H:%M")
            elif next_trip.departure_time_planned is not None:
                attributes["next"] = next_trip.departure_time_planned.strftime("%H:%M")

        return attributes
