"""Teltonika sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from teltasync.modems import ModemStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TeltonikaConfigEntry, TeltonikaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeltonikaSensorEntityDescription(SensorEntityDescription):
    """Describes Teltonika sensor entity."""

    value_fn: Callable[[ModemStatus], StateType]


SENSOR_DESCRIPTIONS: tuple[TeltonikaSensorEntityDescription, ...] = (
    TeltonikaSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        suggested_display_precision=0,
        value_fn=lambda modem: modem.rssi,
    ),
    TeltonikaSensorEntityDescription(
        key="rsrp",
        translation_key="rsrp",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        suggested_display_precision=0,
        value_fn=lambda modem: modem.rsrp,
    ),
    TeltonikaSensorEntityDescription(
        key="rsrq",
        translation_key="rsrq",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        suggested_display_precision=0,
        value_fn=lambda modem: modem.rsrq,
    ),
    TeltonikaSensorEntityDescription(
        key="sinr",
        translation_key="sinr",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        suggested_display_precision=0,
        value_fn=lambda modem: modem.sinr,
    ),
    TeltonikaSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        value_fn=lambda modem: modem.temperature,
    ),
    TeltonikaSensorEntityDescription(
        key="operator",
        translation_key="operator",
        value_fn=lambda modem: modem.operator,
    ),
    TeltonikaSensorEntityDescription(
        key="connection_type",
        translation_key="connection_type",
        value_fn=lambda modem: modem.conntype,
    ),
    TeltonikaSensorEntityDescription(
        key="band",
        translation_key="band",
        value_fn=lambda modem: modem.band,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Teltonika sensor platform."""
    coordinator = entry.runtime_data

    # Track known modems to detect new ones
    known_modems: set[str] = set()

    @callback
    def _async_add_new_modems() -> None:
        """Add sensors for newly discovered modems."""
        current_modems = set(coordinator.data.keys())
        new_modems = current_modems - known_modems

        if new_modems:
            entities = [
                TeltonikaSensorEntity(
                    coordinator,
                    coordinator.device_info,
                    description,
                    modem_id,
                    coordinator.data[modem_id],
                )
                for modem_id in new_modems
                for description in SENSOR_DESCRIPTIONS
            ]
            async_add_entities(entities)
            known_modems.update(new_modems)

    # Add sensors for initial modems
    _async_add_new_modems()

    # Listen for new modems
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_modems))


class TeltonikaSensorEntity(
    CoordinatorEntity[TeltonikaDataUpdateCoordinator], SensorEntity
):
    """Teltonika sensor entity."""

    _attr_has_entity_name = True
    entity_description: TeltonikaSensorEntityDescription

    def __init__(
        self,
        coordinator: TeltonikaDataUpdateCoordinator,
        device_info: DeviceInfo,
        description: TeltonikaSensorEntityDescription,
        modem_id: str,
        modem: ModemStatus,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._modem_id = modem_id
        self._attr_device_info = device_info

        # Create unique ID using entry unique identifier, modem ID, and sensor type
        assert coordinator.config_entry is not None
        entry_unique_id = (
            coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        )
        self._attr_unique_id = f"{entry_unique_id}_{modem_id}_{description.key}"

        # Use translation key for proper naming
        modem_name = modem.name or f"Modem {modem_id}"
        self._modem_name = modem_name
        self._attr_translation_key = description.translation_key
        self._attr_translation_placeholders = {"modem_name": modem_name}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._modem_id in self.coordinator.data

    @property
    def native_value(self) -> StateType:
        """Handle updated data from the coordinator."""
        return self.entity_description.value_fn(self.coordinator.data[self._modem_id])
