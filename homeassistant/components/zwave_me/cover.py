"""Representation of a cover."""
from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform

DEVICE_NAME = ZWaveMePlatform.COVER


async def async_setup_entry(hass, config_entry, async_add_entities):
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

    def close_cover(self, **kwargs):
        """Close cover."""
        self.controller.zwave_api.send_command(self.device.id, "exact?level=0")

    def open_cover(self, **kwargs):
        """Open cover."""
        self.controller.zwave_api.send_command(self.device.id, "exact?level=99")

    def set_cover_position(self, value: float) -> None:
        """Update the current value."""
        self.controller.zwave_api.send_command(
            self.device.id, f"exact?level={str(round(value))}"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self.device.level

    @property
    def supported_features(self) -> int:
        """Return the supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION
