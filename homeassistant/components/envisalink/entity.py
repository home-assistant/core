"""Support for Envisalink devices."""

from typing import Any

from pyenvisalink import EnvisalinkAlarmPanel

from homeassistant.helpers.entity import Entity


class EnvisalinkEntity(Entity):
    """Representation of an Envisalink device."""

    _attr_should_poll = False

    def __init__(
        self, name: str, info: dict[str, Any], controller: EnvisalinkAlarmPanel
    ) -> None:
        """Initialize the device."""
        self._controller = controller
        self._info = info
        self._attr_name = name
