"""Support for IPP sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pyipp import Marker, Printer

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LOCATION, PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
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
from .entity import IPPEntity, async_restore_sensor_entities


@dataclass
class IPPSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Printer], StateType | datetime]


@dataclass
class IPPSensorEntityDescription(
    SensorEntityDescription, IPPSensorEntityDescriptionMixin
):
    """Describes IPP sensor entity."""

    attributes_fn: Callable[[Printer], dict[Any, StateType]] = lambda _: {}


def _get_marker_attributes_fn(
    marker_index: int, attributes_fn: Callable[[Marker], dict[Any, StateType]]
) -> Callable[[Printer], dict[Any, StateType]]:
    return lambda printer: attributes_fn(printer.markers[marker_index])


def _get_marker_value_fn(
    marker_index: int, value_fn: Callable[[Marker], StateType | datetime]
) -> Callable[[Printer], StateType | datetime]:
    return lambda printer: value_fn(printer.markers[marker_index])


PRINTER_SENSORS: dict[str, IPPSensorEntityDescription] = {
    "printer": IPPSensorEntityDescription(
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
            ATTR_URI_SUPPORTED: ",".join(printer.info.printer_uri_supported),
        },
        value_fn=lambda printer: printer.state.printer_state,
    ),
    "uptime": IPPSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda printer: (utcnow() - timedelta(seconds=printer.info.uptime)),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IPP sensor based on a config entry."""
    coordinator: IPPDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.last_update_success:
        async_restore_sensor_entities(
            hass,
            entry,
            async_add_entities,
            PRINTER_SENSORS,
            IPPSensor,
        )
    else:
        sensors: list[SensorEntity] = [
            IPPSensor(
                coordinator,
                description,
            )
            for description in PRINTER_SENSORS.values()
        ]

        for index, marker in enumerate(coordinator.data.markers):
            sensors.append(
                IPPSensor(
                    coordinator,
                    IPPSensorEntityDescription(
                        key=f"marker_{index}",
                        name=marker.name,
                        icon="mdi:water",
                        native_unit_of_measurement=PERCENTAGE,
                        attributes_fn=_get_marker_attributes_fn(
                            index,
                            lambda marker: {
                                ATTR_MARKER_HIGH_LEVEL: marker.high_level,
                                ATTR_MARKER_LOW_LEVEL: marker.low_level,
                                ATTR_MARKER_TYPE: marker.marker_type,
                            },
                        ),
                        value_fn=_get_marker_value_fn(index, lambda marker: marker.level),
                    ),
                )
            )

        async_add_entities(sensors)


class IPPSensor(IPPEntity, RestoreSensor):
    """Defines an IPP sensor."""

    entity_description: IPPSensorEntityDescription

    async def _async_restore_state(self) -> None:
        """Restore state."""
        if restored_data := await self.async_get_last_sensor_data():
            print(restored_data)
            self._attr_native_value = restored_data.native_value

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await self._async_restore_state()
        await super().async_added_to_hass()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the entity."""
        if self.coordinator.data is not None:
            return self.entity_description.attributes_fn(self.coordinator.data)

        return {}

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            return self.entity_description.value_fn(self.coordinator.data)

        return self._attr_native_value
