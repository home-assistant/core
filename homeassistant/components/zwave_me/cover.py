"""Representation of a cover."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform

DEVICE_NAME = ZWaveMePlatform.COVER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform."""

    @callback
    def add_new_device(new_device):
        controller = hass.data[DOMAIN][config_entry.entry_id]
        cover = ZWaveMeCover(controller, new_device)

        async_add_entities(
            [
                cover,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeCover(ZWaveMeEntity, CoverEntity):
    """Representation of a ZWaveMe Multilevel Cover."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self.controller.zwave_api.send_command(self.device.id, "exact?level=0")

    def open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        self.controller.zwave_api.send_command(self.device.id, "exact?level=99")

    def set_cover_position(self, **kwargs: Any) -> None:
        """Update the current value."""
        value = kwargs[ATTR_POSITION]
        self.controller.zwave_api.send_command(
            self.device.id, f"exact?level={str(min(value, 99))}"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self.device.level == 99:  # Scale max value
            return 100

        return self.device.level
