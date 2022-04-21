"""Binary sensors for Moonraker API integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connector import APIConnector, generate_signal
from .const import (
    DATA_CONNECTOR,
    DOMAIN,
    SIGNAL_UPDATE_EXTRUDER,
    SIGNAL_UPDATE_HEAT_BED,
    SIGNAL_UPDATE_PRINT_STATUS,
    SIGNAL_UPDATE_VIRTUAL_SDCARD,
)
from .entity import MoonrakerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Moonraker entities."""
    connector: APIConnector = hass.data[DOMAIN][config_entry.entry_id][DATA_CONNECTOR]
    entities: list[SensorEntity] = [
        MoonrakerGenericSensor(config_entry, connector, x) for x in SENSOR_TYPES
    ]
    async_add_entities(entities)


@dataclass
class MoonrakerSensorKeysMixin:
    """A class that describes binary sensor required keys."""

    value: Callable[[Any], Any] | None
    signal: str


@dataclass
class MoonrakerSensorDescription(SensorEntityDescription, MoonrakerSensorKeysMixin):
    """A class that describes binary sensors."""


SENSOR_TYPES = (
    MoonrakerSensorDescription(
        key="extruder_temperature",
        name="Extruder Temperature",
        signal=SIGNAL_UPDATE_EXTRUDER,
        value=lambda params: round(params["temperature"], 1),
        entity_registry_enabled_default=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
    ),
    MoonrakerSensorDescription(
        key="extruder_target",
        name="Extruder Target Temperature",
        signal=SIGNAL_UPDATE_EXTRUDER,
        value=lambda params: round(params["target"], 1),
        entity_registry_enabled_default=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
    ),
    MoonrakerSensorDescription(
        key="bed_temperature",
        name="Bed Temperature",
        signal=SIGNAL_UPDATE_HEAT_BED,
        value=lambda params: round(params["temperature"], 1),
        entity_registry_enabled_default=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radiator",
    ),
    MoonrakerSensorDescription(
        key="bed_target",
        name="Bed Target Temperature",
        signal=SIGNAL_UPDATE_HEAT_BED,
        value=lambda params: round(params["target"], 1),
        entity_registry_enabled_default=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:radiator",
    ),
    MoonrakerSensorDescription(
        key="print_progress",
        name="Print Progress",
        signal=SIGNAL_UPDATE_VIRTUAL_SDCARD,
        value=lambda params: round(params["progress"] * 100),
        entity_registry_enabled_default=True,
        native_unit_of_measurement=PERCENTAGE,
    ),
    MoonrakerSensorDescription(
        key="print_duration",
        name="Print Duration",
        signal=SIGNAL_UPDATE_PRINT_STATUS,
        value=lambda params: str(
            datetime.timedelta(seconds=round(params["print_duration"]))
        ),
        entity_registry_enabled_default=True,
        icon="mdi:clock-outline",
    ),
    MoonrakerSensorDescription(
        key="print_file",
        name="Print File",
        signal=SIGNAL_UPDATE_PRINT_STATUS,
        value=lambda params: params["filename"],
        entity_registry_enabled_default=True,
        icon="mdi:file",
    ),
)


class MoonrakerGenericSensor(MoonrakerEntity, SensorEntity):
    """Binary sensor representing printing state."""

    entity_description: MoonrakerSensorDescription

    def __init__(
        self,
        entry: ConfigEntry,
        connector: APIConnector,
        description: MoonrakerSensorDescription,
    ) -> None:
        """Initialize a new printing binary sensor."""
        super().__init__(entry, connector, description.name)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )

    async def async_added_to_hass(self) -> None:
        """Configure entity update handlers."""
        await super().async_added_to_hass()

        @callback
        def update_state(params: Any) -> None:
            """Entity state update."""
            try:
                if self.entity_description.value:
                    self._attr_native_value = self.entity_description.value(params)
                self.module_available = True
            except KeyError:
                pass
            else:
                self.async_write_ha_state()

        signal = generate_signal(self.entity_description.signal, self.entry.entry_id)
        self.async_on_remove(async_dispatcher_connect(self.hass, signal, update_state))
