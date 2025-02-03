"""Define the base entity for the Gryf Smart integration."""

from __future__ import annotations

import logging

from pygryfsmart.api import GryfApi
from pygryfsmart.device import _GryfDevice

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class _GryfSmartEntityBase(Entity):
    """Base Entity for Gryf Smart."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _api: GryfApi
    _device: _GryfDevice
    _attr_unique_id: str | None

    def __init__(self):
        self._attr_unique_id = self._device.name
        self._attr_name = self._device.name

    @property
    def name(self) -> str:
        return self._device.name

    # @property
    # def available(self) -> bool:
    #     return self._device.available

    # async def async_added_to_hass(self) -> None:
