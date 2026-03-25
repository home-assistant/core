"""Support for Velux exterior heating number entities."""

from __future__ import annotations

from pyvlx import ExteriorHeating, Intensity

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for the Velux platform."""
    pyvlx = config_entry.runtime_data
    async_add_entities(
        VeluxExteriorHeatingNumber(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, ExteriorHeating)
    )


class VeluxExteriorHeatingNumber(VeluxEntity, NumberEntity):
    """Representation of an exterior heating intensity control."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = None

    node: ExteriorHeating

    @property
    def native_value(self) -> float | None:
        """Return the current heating intensity in percent."""
        return (
            self.node.intensity.intensity_percent if self.node.intensity.known else None
        )

    @wrap_pyvlx_call_exceptions
    async def async_set_native_value(self, value: float) -> None:
        """Set the heating intensity."""
        await self.node.set_intensity(
            Intensity(intensity_percent=round(value)),
            wait_for_completion=True,
        )
