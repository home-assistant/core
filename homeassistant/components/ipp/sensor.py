"""Support for IPP sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LOCATION, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

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
    DOMAIN,
)
from .coordinator import IPPDataUpdateCoordinator
from .entity import IPPEntity


@dataclass
class IPPSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], StateType | datetime]


@dataclass
class IPPSensorEntityDescription(
    SensorEntityDescription, IPPSensorEntityDescriptionMixin
):
    """Describes IPP sensor entity."""

    attributes_fn: Callable[[Any], dict[Any, StateType]] = lambda _: {}


PRINTER_SENSORS: tuple[IPPSensorEntityDescription, ...] = (
    IPPSensorEntityDescription(
        key="printer",
        name=None,
        translation_key="printer",
        icon="mdi:printer",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "printing", "stopped"],
        attributes_fn=lambda printer: {
            ATTR_INFO: printer.info.printer_info,
            ATTR_SERIAL: printer.info.serial,
            ATTR_LOCATION: printer.info.location,
            ATTR_STATE_MESSAGE: printer.state.message,
            ATTR_STATE_REASON: printer.state.reasons,
            ATTR_COMMAND_SET: printer.info.command_set,
            ATTR_URI_SUPPORTED: printer.info.printer_uri_supported,
        },
        value_fn=lambda printer: printer.state.printer_state,
    ),
    IPPSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda printer: (utcnow() - timedelta(seconds=printer.info.uptime)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IPP sensor based on a config entry."""
    coordinator: IPPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # config flow sets this to either UUID, serial number or None
    if (unique_id := entry.unique_id) is None:
        unique_id = entry.entry_id

    sensors: list[SensorEntity] = []

    sensors.extend(
        [
            IPPSensor(
                unique_id,
                coordinator,
                description,
            )
            for description in PRINTER_SENSORS
        ]
    )

    for index, marker in enumerate(coordinator.data.markers):
        sensors.append(
            IPPMarkerSensor(
                index,
                unique_id,
                coordinator,
                IPPSensorEntityDescription(
                    key=f"marker_{index}",
                    name=marker.name,
                    icon="mdi:water",
                    native_unit_of_measurement=PERCENTAGE,
                    attributes_fn=lambda marker: {
                        ATTR_MARKER_HIGH_LEVEL: marker.high_level,
                        ATTR_MARKER_LOW_LEVEL: marker.low_level,
                        ATTR_MARKER_TYPE: marker.marker_type,
                    },
                    value_fn=lambda marker: marker.level,
                ),
            )
        )

    async_add_entities(sensors, True)


class IPPSensor(IPPEntity, SensorEntity):
    """Defines an IPP sensor."""

    entity_description: IPPSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        coordinator: IPPDataUpdateCoordinator,
        description: IPPSensorEntityDescription,
    ) -> None:
        """Initialize IPP sensor."""
        self.entity_description = description

        super().__init__(
            device_id,
            coordinator,
        )

        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(self.coordinator.data)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class IPPMarkerSensor(IPPEntity, SensorEntity):
    """Defines an IPP marker sensor."""

    entity_description: IPPSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        marker_index: int,
        device_id: str,
        coordinator: IPPDataUpdateCoordinator,
        description: IPPSensorEntityDescription,
    ) -> None:
        """Initialize IPP marker sensor."""
        self.entity_description = description
        self.marker_index = marker_index

        super().__init__(
            device_id,
            coordinator,
        )

        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        return self.entity_description.attributes_fn(
            self.coordinator.data.markers[self.marker_index]
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.markers[self.marker_index]
        )
