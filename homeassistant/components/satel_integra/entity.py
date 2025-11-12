"""Satel Integra base entity."""

from __future__ import annotations

from satel_integra.satel_integra import AsyncSatel

from homeassistant.helpers.entity import Entity


class SatelIntegraEntity(Entity):
    """Defines a base Satel Integra entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, controller: AsyncSatel, device_number: int) -> None:
        """Initialize the Satel Integra entity."""
        self._satel = controller
        self._device_number = device_number
