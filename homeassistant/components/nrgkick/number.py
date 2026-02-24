"""Number platform for NRGkick."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nrgkick_api.const import (
    CONTROL_KEY_CURRENT_SET,
    CONTROL_KEY_ENERGY_LIMIT,
    CONTROL_KEY_PHASE_COUNT,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 1

MIN_CHARGING_CURRENT = 6


def _get_current_set_max(data: NRGkickData) -> float:
    """Return the maximum current setpoint.

    Uses the lower of the device rated current and the connector max current.
    The device always has a rated current; the connector may be absent.
    """
    rated: float = data.info["general"]["rated_current"]
    connector_max = data.info.get("connector", {}).get("max_current")
    if connector_max is None:
        return rated
    return min(rated, float(connector_max))


def _get_phase_count_max(data: NRGkickData) -> float:
    """Return the maximum phase count based on the attached connector."""
    connector_phases = data.info.get("connector", {}).get("phase_count")
    if connector_phases is None:
        return 3.0
    return float(connector_phases)


@dataclass(frozen=True, kw_only=True)
class NRGkickNumberEntityDescription(NumberEntityDescription):
    """Class describing NRGkick number entities."""

    value_fn: Callable[[NRGkickData], float | None]
    set_value_fn: Callable[[NRGkickDataUpdateCoordinator, float], Awaitable[Any]]
    max_value_fn: Callable[[NRGkickData], float] | None = None


NUMBERS: tuple[NRGkickNumberEntityDescription, ...] = (
    NRGkickNumberEntityDescription(
        key="current_set",
        translation_key="current_set",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_CHARGING_CURRENT,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: data.control.get(CONTROL_KEY_CURRENT_SET),
        set_value_fn=lambda coordinator, value: coordinator.api.set_current(value),
        max_value_fn=_get_current_set_max,
    ),
    NRGkickNumberEntityDescription(
        key="energy_limit",
        translation_key="energy_limit",
        device_class=NumberDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        native_min_value=0,
        native_max_value=100000,
        native_step=1,
        mode=NumberMode.BOX,
        value_fn=lambda data: data.control.get(CONTROL_KEY_ENERGY_LIMIT),
        set_value_fn=lambda coordinator, value: coordinator.api.set_energy_limit(
            int(value)
        ),
    ),
    NRGkickNumberEntityDescription(
        key="phase_count",
        translation_key="phase_count",
        native_min_value=1,
        native_max_value=3,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda data: data.control.get(CONTROL_KEY_PHASE_COUNT),
        set_value_fn=lambda coordinator, value: coordinator.api.set_phase_count(
            int(value)
        ),
        max_value_fn=_get_phase_count_max,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick number entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NRGkickNumber(coordinator, description) for description in NUMBERS
    )


class NRGkickNumber(NRGkickEntity, NumberEntity):
    """Representation of an NRGkick number entity."""

    entity_description: NRGkickNumberEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        description: NRGkickNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if self.entity_description.max_value_fn is not None:
            data = self.coordinator.data
            if TYPE_CHECKING:
                assert data is not None
            return self.entity_description.max_value_fn(data)
        return super().native_max_value

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        data = self.coordinator.data
        if TYPE_CHECKING:
            assert data is not None
        return self.entity_description.value_fn(data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self._async_call_api(
            self.entity_description.set_value_fn(self.coordinator, value)
        )
