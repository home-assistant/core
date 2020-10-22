"""Support for Vera cover - curtains, rollershutters etc."""
from typing import Any, Callable, List

import pyvera as veraApi

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import VeraDevice
from .common import ControllerData, get_controller_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraCover(device, controller_data)
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ]
    )


class VeraCover(VeraDevice[veraApi.VeraCurtain], CoverEntity):
    """Representation a Vera Cover."""

    def __init__(
        self, vera_device: veraApi.VeraCurtain, controller_data: ControllerData
    ):
        """Initialize the Vera device."""
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def current_cover_position(self) -> int:
        """
        Return current position of cover.

        0 is closed, 100 is fully open.
        """
        position = self.vera_device.get_level()
        if position <= 5:
            return 0
        if position >= 95:
            return 100
        return position

    def set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        self.vera_device.set_level(kwargs.get(ATTR_POSITION))
        self.schedule_update_ha_state()

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        if self.current_cover_position is not None:
            return self.current_cover_position == 0

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.vera_device.open()
        self.schedule_update_ha_state()

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.vera_device.close()
        self.schedule_update_ha_state()

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self.vera_device.stop()
        self.schedule_update_ha_state()
