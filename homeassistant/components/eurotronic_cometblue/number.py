"""Comet Blue number integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from eurotronic_cometblue_ha import AsyncCometBlue

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .climate import MAX_TEMP, MIN_TEMP
from .coordinator import CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity

LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CometBlueRequiredKeysMixin:
    """Mixin for required keys."""

    cometblue_key: str
    set_fn: Callable[[AsyncCometBlue], Any]


@dataclass(frozen=True, kw_only=True)
class CometBlueNumberEntityDescription(
    NumberEntityDescription, CometBlueRequiredKeysMixin
):
    """Describes a Comet Blue number entity."""


DESCRIPTIONS = [
    CometBlueNumberEntityDescription(
        key="offset",
        cometblue_key="tempOffset",
        translation_key="offset",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=-5.0,
        native_max_value=5.0,
        native_step=PRECISION_HALVES,
        entity_registry_enabled_default=False,
    ),
    CometBlueNumberEntityDescription(
        key="target_temp_low",
        cometblue_key="targetTempLow",
        translation_key="target_temp_low",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_step=PRECISION_HALVES,
        entity_registry_enabled_default=False,
    ),
    CometBlueNumberEntityDescription(
        key="target_temp_high",
        cometblue_key="targetTempHigh",
        translation_key="target_temp_high",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_step=PRECISION_HALVES,
        entity_registry_enabled_default=False,
    ),
    CometBlueNumberEntityDescription(
        key="window_open_minutes",
        cometblue_key="windowOpenMinutes",
        translation_key="window_open_minutes",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=5.0,
        native_max_value=15.0,
        native_step=5.0,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gardena Bluetooth number based on a config entry."""
    coordinator: CometBlueDataUpdateCoordinator = entry.runtime_data

    entities: list[CometBlueNumberEntity] = [
        CometBlueNumberEntity(coordinator, description) for description in DESCRIPTIONS
    ]

    async_add_entities(entities)


class CometBlueNumberEntity(CometBlueBluetoothEntity, NumberEntity):
    """Representation of a number."""

    entity_description: CometBlueNumberEntityDescription

    def __init__(
        self,
        coordinator: CometBlueDataUpdateCoordinator,
        description: CometBlueNumberEntityDescription,
    ) -> None:
        """Initialize CometBlueNumberEntity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.coordinator.data.get(self.entity_description.cometblue_key)

    async def async_set_native_value(self, value: float) -> None:
        """Update to the device."""

        await self.coordinator.send_command(
            "set_temperature_async",
            {
                "values": {
                    # manual temperature always needs to be set, otherwise TRV will turn OFF
                    "manualTemp": self.coordinator.data["manualTemp"],
                    self.entity_description.cometblue_key: value,
                }
            },
            self.entity_id,
        )
        await self.coordinator.async_request_refresh()
