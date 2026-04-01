"""Support for AVM FRITZ!SmartHome number entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from pyfritzhome import FritzhomeDevice

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_STATE_MANUAL_OPEN_WINDOW_PERIOD, DEFAULT_OPEN_WINDOW_PERIOD
from .coordinator import FritzboxConfigEntry
from .entity import FritzBoxDeviceEntity
from .model import FritzEntityDescriptionMixinBase

# Coordinator handles data updates, so we can allow unlimited parallel updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome template from ConfigEntry."""
    coordinator = entry.runtime_data

    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            [
                FritzBoxNumber(coordinator, ain, description)
                for ain in devices
                for description in NUMBERS
                if description.suitable(coordinator.data.devices[ain])
            ]
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


@dataclass(frozen=True, kw_only=True)
class FritzNumberEntityDescription(
    NumberEntityDescription, FritzEntityDescriptionMixinBase
):
    """Base description mixin for Fritz!Smarthome entities."""

    value_fn: Callable[[FritzhomeDevice], float | None]
    set_value_fn: Callable[[FritzhomeDevice, float], None]
    native_default_value: float | None = None


NUMBERS: Final[tuple[FritzNumberEntityDescription, ...]] = (
    FritzNumberEntityDescription(
        key="manual_open_window_period",
        translation_key="manual_open_window_period",
        device_class=NumberDeviceClass.DURATION,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_default_value=DEFAULT_OPEN_WINDOW_PERIOD,
        native_min_value=1.0,
        native_max_value=24.0 * 60 * 60,
        suitable=lambda device: device.has_thermostat,
        value_fn=lambda device: getattr(
            device, ATTR_STATE_MANUAL_OPEN_WINDOW_PERIOD, None
        ),
        set_value_fn=lambda device, value: setattr(
            device, ATTR_STATE_MANUAL_OPEN_WINDOW_PERIOD, value
        ),
    ),
)


class FritzBoxNumber(FritzBoxDeviceEntity, NumberEntity):
    """The entity class for FRITZ!SmartHome number helpers."""

    entity_description: FritzNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value via entity description method."""
        await self.hass.async_add_executor_job(
            self.entity_description.set_value_fn, self.data, value
        )
        await self.coordinator.async_refresh()

    @property
    def native_value(self) -> float | None:
        """Get the native value."""
        value = self.entity_description.value_fn(self.data)
        return (
            value if value is not None else self.entity_description.native_default_value
        )
