"""Support for Lutron Homeworks Series 4 and 8 systems."""

from __future__ import annotations

from pyhomeworks.pyhomeworks import Homeworks

from homeassistant.helpers.entity import Entity

from .util import calculate_unique_id


class HomeworksEntity(Entity):
    """Base class of a Homeworks device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        controller: Homeworks,
        controller_id: str,
        addr: str,
        idx: int,
        name: str | None,
    ) -> None:
        """Initialize Homeworks device."""
        self._addr = addr
        self._idx = idx
        self._controller_id = controller_id
        self._attr_name = name
        self._attr_unique_id = calculate_unique_id(
            self._controller_id, self._addr, self._idx
        )
        self._controller = controller
        self._attr_extra_state_attributes = {"homeworks_address": self._addr}
