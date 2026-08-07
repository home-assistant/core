"""Sensor for De Lijn (Flemish public transport) departure information."""

from datetime import datetime
from typing import Any, override

from pydelijn import Passage
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY
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
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import DeLijnConfigEntry, DeLijnCoordinator

PARALLEL_UPDATES = 0

CONF_NEXT_DEPARTURE = "next_departure"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration into config entries."""
    for departure in config[CONF_NEXT_DEPARTURE]:
        stop_id = departure[CONF_STOP_ID]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_API_KEY: config[CONF_API_KEY],
                CONF_STOP_ID: stop_id,
                CONF_NUMBER_OF_DEPARTURES: departure[CONF_NUMBER_OF_DEPARTURES],
            },
        )
        reason = result.get("reason")
        if (
            result.get("type") is FlowResultType.ABORT
            and reason != "already_configured"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{stop_id}_{reason}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "De Lijn",
                    "stop_id": stop_id,
                },
            )

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "De Lijn"},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeLijnConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the De Lijn sensor from a config entry."""
    async_add_entities([DeLijnSensor(entry.runtime_data, entry)])


def _due_in_minutes(due_at: datetime | None) -> int | None:
    """Return the number of minutes from now until due_at."""
    if due_at is None:
        return None
    return round((due_at - dt_util.utcnow()).total_seconds() / 60)


def _passage_attributes(index: int, passage: Passage) -> dict[str, Any]:
    """Return the legacy attribute mapping for a single passage."""
    line = passage.line
    return {
        "passage": index,
        "line_number": line.number,
        "direction": passage.direction,
        "final_destination": passage.destination,
        "due_at_schedule": (
            passage.due_at_schedule.isoformat() if passage.due_at_schedule else None
        ),
        "due_at_realtime": (
            passage.due_at_realtime.isoformat() if passage.due_at_realtime else None
        ),
        "due_in_min": _due_in_minutes(passage.due_at),
        "is_realtime": passage.is_realtime,
        "cancelled": passage.cancelled,
        "line_number_public": line.public_number,
        "line_desc": line.description,
        "line_transport_type": line.transport_type,
        "line_number_colourFront": line.colour_front_hex,
        "line_number_colourFrontHex": line.colour_front_hex,
        "line_number_colourBack": line.colour_back_hex,
        "line_number_colourBackHex": line.colour_back_hex,
        "line_number_colourFrontBorder": line.colour_front_border_hex,
        "line_number_colourFrontBorderHex": line.colour_front_border_hex,
        "line_number_colourBackBorder": line.colour_back_border_hex,
        "line_number_colourBackBorderHex": line.colour_back_border_hex,
    }


class DeLijnSensor(CoordinatorEntity[DeLijnCoordinator], SensorEntity):
    """Representation of the next De Lijn departure at a stop."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: DeLijnCoordinator, entry: DeLijnConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        stop_number = entry.data[CONF_STOP_NUMBER]
        self._attr_unique_id = f"{entry.unique_id}_next_departure"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_number)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the due time of the next passage."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data[0].due_at

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return backward-compatible attributes for the community Lovelace card."""
        passages = self.coordinator.data
        if not passages:
            return {
                "line_number_public": None,
                "line_transport_type": None,
                "final_destination": None,
                "due_at_schedule": None,
                "due_at_realtime": None,
                "is_realtime": None,
                "cancelled": None,
                "next_passages": [],
            }

        first = passages[0]
        return {
            "line_number_public": first.line.public_number,
            "line_transport_type": first.line.transport_type,
            "final_destination": first.destination,
            "due_at_schedule": (
                first.due_at_schedule.isoformat() if first.due_at_schedule else None
            ),
            "due_at_realtime": (
                first.due_at_realtime.isoformat() if first.due_at_realtime else None
            ),
            "is_realtime": first.is_realtime,
            "cancelled": first.cancelled,
            "next_passages": [
                _passage_attributes(index, passage)
                for index, passage in enumerate(passages)
            ],
        }
