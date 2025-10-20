"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from ns_api import Trip
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


def _get_departure_time(trip: Trip | None) -> datetime | None:
    """Get next departure time from trip data."""
    if not trip:
        return None
    actual = getattr(trip, "departure_time_actual", None)
    planned = getattr(trip, "departure_time_planned", None)
    return actual or planned


def _get_time_str(time: datetime | None) -> str | None:
    """Get time as string."""
    return time.strftime("%H:%M") if time else None


def _get_route(trip: Trip | None) -> list[str]:
    """Get the route as a list of station names from trip data."""
    if not trip:
        return []
    trip_parts = trip.trip_parts or []
    if not trip_parts:
        return []
    route = []
    departure = trip.departure
    if departure:
        route.append(departure)
    route.extend(part.destination for part in trip_parts)
    return route


def _get_delay(planned: datetime | None, actual: datetime | None) -> bool:
    """Return True if delay is present, False otherwise."""
    return bool(planned and actual and planned != actual)


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
        return _get_departure_time(first_trip)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        first_trip = self.coordinator.data.first_trip
        next_trip = self.coordinator.data.next_trip

        if not first_trip:
            return None

        route = _get_route(first_trip)
        status = getattr(first_trip, "status", None)

        # Static attributes
        return {
            "going": getattr(first_trip, "going", None),
            "departure_time_planned": _get_time_str(
                getattr(first_trip, "departure_time_planned", None)
            ),
            "departure_time_actual": _get_time_str(
                getattr(first_trip, "departure_time_actual", None)
            ),
            "departure_delay": _get_delay(
                getattr(first_trip, "departure_time_planned", None),
                getattr(first_trip, "departure_time_actual", None),
            ),
            "departure_platform_planned": getattr(
                first_trip, "departure_platform_planned", None
            ),
            "departure_platform_actual": getattr(
                first_trip, "departure_platform_actual", None
            ),
            "arrival_time_planned": _get_time_str(
                getattr(first_trip, "arrival_time_planned", None)
            ),
            "arrival_time_actual": _get_time_str(
                getattr(first_trip, "arrival_time_actual", None)
            ),
            "arrival_delay": _get_delay(
                getattr(first_trip, "arrival_time_planned", None),
                getattr(first_trip, "arrival_time_actual", None),
            ),
            "arrival_platform_planned": getattr(
                first_trip, "arrival_platform_planned", None
            ),
            "arrival_platform_actual": getattr(
                first_trip, "arrival_platform_actual", None
            ),
            "next": _get_time_str(_get_departure_time(next_trip)),
            "status": status.lower() if status else None,
            "transfers": getattr(first_trip, "nr_transfers", 0),
            "route": route,
            "remarks": None,
        }
