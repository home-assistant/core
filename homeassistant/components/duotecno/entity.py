"""Support for Velbus devices."""
from __future__ import annotations

from duotecno.unit import BaseUnit

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class DuotecnoEntity(Entity):
    """Representation of a Duotecno entity."""

    _attr_should_poll: bool = False
    _unit: BaseUnit

    def __init__(self, unit) -> None:
        """Initialize a Duotecno entity."""
        self._unit = unit
        self._attr_name = unit.get_name()
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, str(unit.get_node_address())),
            },
            manufacturer="Duotecno",
            name=unit.get_node_name(),
        )
        self._attr_unique_id = f"{unit.get_node_address()}-{unit.get_number()}"

    async def async_added_to_hass(self) -> None:
        """When added to hass."""
        self._unit.on_status_update(self._on_update)

    async def _on_update(self) -> None:
        """When a unit has an update."""
        self.async_write_ha_state()
