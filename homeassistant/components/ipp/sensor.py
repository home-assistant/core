"""Support for IPP sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pyipp import Marker, Printer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import ATTR_LOCATION, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_COMMAND_SET,
    ATTR_INFO,
    ATTR_MARKER_HIGH_LEVEL,
    ATTR_MARKER_LOW_LEVEL,
    ATTR_MARKER_TYPE,
    ATTR_SERIAL,
    ATTR_STATE_MESSAGE,
    ATTR_STATE_REASON,
    ATTR_URI_SUPPORTED,
)
from .coordinator import IPPConfigEntry, IPPDataUpdateCoordinator
from .entity import IPPEntity


@dataclass(frozen=True, kw_only=True)
class IPPSensorEntityDescription(SensorEntityDescription):
    """Describes IPP sensor entity."""

    value_fn: Callable[[Printer], StateType | datetime]
    attributes_fn: Callable[[Printer], dict[Any, StateType]] = lambda _: {}


@dataclass(frozen=True, kw_only=True)
class IPPPageCountSensorEntityDescription(SensorEntityDescription):
    """Describes IPP page count sensor entity."""

    ipp_attribute: str


def _get_marker_attributes_fn(
    marker_index: int, attributes_fn: Callable[[Marker], dict[Any, StateType]]
) -> Callable[[Printer], dict[Any, StateType]]:
    return lambda printer: attributes_fn(printer.markers[marker_index])


def _get_marker_value_fn(
    marker_index: int, value_fn: Callable[[Marker], StateType | datetime]
) -> Callable[[Printer], StateType | datetime]:
    return lambda printer: value_fn(printer.markers[marker_index])


PRINTER_SENSORS: tuple[IPPSensorEntityDescription, ...] = (
    IPPSensorEntityDescription(
        key="printer",
        name=None,
        translation_key="printer",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "printing", "stopped"],
        attributes_fn=lambda printer: {
            ATTR_INFO: printer.info.printer_info,
            ATTR_SERIAL: printer.info.serial,
            ATTR_LOCATION: printer.info.location,
            ATTR_STATE_MESSAGE: printer.state.message,
            ATTR_STATE_REASON: printer.state.reasons,
            ATTR_COMMAND_SET: printer.info.command_set,
            ATTR_URI_SUPPORTED: ",".join(printer.info.printer_uri_supported),
        },
        value_fn=lambda printer: printer.state.printer_state,
    ),
    IPPSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda printer: printer.booted_at,
    ),
)

PAGE_COUNT_SENSORS: tuple[IPPPageCountSensorEntityDescription, ...] = (
    IPPPageCountSensorEntityDescription(
        key="pages_completed",
        translation_key="pages_completed",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        ipp_attribute="printer-pages-completed",
    ),
    IPPPageCountSensorEntityDescription(
        key="impressions_completed",
        translation_key="impressions_completed",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        ipp_attribute="printer-impressions-completed",
    ),
    IPPPageCountSensorEntityDescription(
        key="media_sheets_completed",
        translation_key="media_sheets_completed",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        ipp_attribute="printer-media-sheets-completed",
    ),
    IPPPageCountSensorEntityDescription(
        key="impressions_completed_monochrome",
        translation_key="impressions_completed_monochrome",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        ipp_attribute="printer-impressions-completed-col/monochrome",
    ),
    IPPPageCountSensorEntityDescription(
        key="impressions_completed_full_color",
        translation_key="impressions_completed_full_color",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        ipp_attribute="printer-impressions-completed-col/full-color",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IPPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IPP sensor based on a config entry."""
    coordinator = entry.runtime_data
    sensors: list[SensorEntity] = [
        IPPSensor(
            coordinator,
            description,
        )
        for description in PRINTER_SENSORS
    ]

    for index, marker in enumerate(coordinator.data.markers):
        sensors.append(
            IPPSensor(
                coordinator,
                IPPSensorEntityDescription(
                    key=f"marker_{index}",
                    name=marker.name,
                    translation_key="marker",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    attributes_fn=_get_marker_attributes_fn(
                        index,
                        lambda marker: {
                            ATTR_MARKER_HIGH_LEVEL: marker.high_level,
                            ATTR_MARKER_LOW_LEVEL: marker.low_level,
                            ATTR_MARKER_TYPE: marker.marker_type,
                        },
                    ),
                    value_fn=_get_marker_value_fn(
                        index,
                        lambda marker: marker.level if marker.level >= 0 else None,
                    ),
                ),
            )
        )

    sensors.extend(
        IPPPageCountSensor(coordinator, description)
        for description in PAGE_COUNT_SENSORS
        if description.ipp_attribute in coordinator.page_counts
    )

    async_add_entities(sensors, True)


class IPPSensor(IPPEntity, SensorEntity):
    """Defines an IPP sensor."""

    entity_description: IPPSensorEntityDescription

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class IPPPageCountSensor(IPPEntity, SensorEntity):
    """Defines an IPP page count sensor."""

    entity_description: IPPPageCountSensorEntityDescription

    def __init__(
        self,
        coordinator: IPPDataUpdateCoordinator,
        description: IPPPageCountSensorEntityDescription,
    ) -> None:
        """Initialize the page count sensor."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.page_counts.get(self.entity_description.ipp_attribute)
