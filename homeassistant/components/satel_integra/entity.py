"""Satel Integra base entity."""

from __future__ import annotations

from satel_integra.satel_integra import AsyncSatel

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class SatelIntegraEntity(Entity):
    """Defines a base Satel Integra entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        controller: AsyncSatel,
        unique_id: str,
        device_number: int,
        device_name: str,
    ) -> None:
        """Initialize the Satel Integra entity."""
        self._satel = controller
        self._device_number = device_number
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            name=device_name, identifiers={(DOMAIN, self._attr_unique_id)}
        )
