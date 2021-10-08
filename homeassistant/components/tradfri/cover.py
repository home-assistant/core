"""Support for IKEA Tradfri covers."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pytradfri.command import Command

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import TradfriBaseDevice
from .const import ATTR_MODEL, CONF_GATEWAY_ID, DEVICES, DOMAIN, KEY_API


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load Tradfri covers based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data[KEY_API]
    devices = tradfri_data[DEVICES]

    covers = [dev for dev in devices if dev.has_blind_control]
    if covers:
        async_add_entities(TradfriCover(cover, api, gateway_id) for cover in covers)


class TradfriCover(TradfriBaseDevice, CoverEntity):
    """The platform class required by Home Assistant."""

    def __init__(
        self,
        device: Command,
        api: Callable[[Command | list[Command]], Any],
        gateway_id: str,
    ) -> None:
        """Initialize a cover."""
        super().__init__(device, api, gateway_id)
        self._attr_unique_id = f"{gateway_id}-{device.id}"

        self._refresh(device)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        return {ATTR_MODEL: self._device.device_info.model_number}

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if not self._device_data:
            return None
        return 100 - cast(int, self._device_data.current_cover_position)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_state(100 - kwargs[ATTR_POSITION]))

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_state(0))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if not self._device_control:
            return
        await self._api(self._device_control.set_state(100))

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if not self._device_control:
            return
        await self._api(self._device_control.trigger_blind())

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    def _refresh(self, device: Command) -> None:
        """Refresh the cover data."""
        super()._refresh(device)
        self._device = device

        # Caching of BlindControl and cover object
        self._device_control = device.blind_control
        self._device_data = device.blind_control.blinds[0]
