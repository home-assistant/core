"""Support for ESPHome infrared proxy remote components."""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
import logging
from typing import Any

from aioesphomeapi import (
    EntityInfo,
    EntityState,
    InfraredProxyCapability,
    InfraredProxyInfo,
)

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .entity import EsphomeEntity, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class EsphomeInfraredProxy(EsphomeEntity[InfraredProxyInfo, EntityState], RemoteEntity):
    """An infrared proxy remote implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        capabilities = static_info.capabilities

        # Set supported features based on capabilities
        features = RemoteEntityFeature(0)
        if capabilities & InfraredProxyCapability.RECEIVER:
            features |= RemoteEntityFeature.LEARN_COMMAND
        self._attr_supported_features = features

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Infrared proxy entities should go available directly
            # when the device comes online.
            self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if remote is on."""
        # ESPHome infrared proxies are always on when available
        return self.available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote on."""
        # ESPHome infrared proxies are always on, nothing to do
        _LOGGER.debug("Turn on called for %s (no-op)", self.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote off."""
        # ESPHome infrared proxies cannot be turned off
        _LOGGER.debug("Turn off called for %s (no-op)", self.name)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        # This method would need to parse command data and timing parameters
        # For now, we'll raise an error as this requires more complex implementation
        raise HomeAssistantError(
            "Direct command sending not yet implemented for ESPHome infrared proxy. "
            "Use the infrared_proxy_transmit service instead."
        )

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        # Learning is handled through the receive event subscription
        # which is managed at the entry_data level
        raise HomeAssistantError(
            "Learning commands is handled automatically through receive events. "
            "Listen for esphome_infrared_proxy_received events instead."
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=InfraredProxyInfo,
    entity_type=EsphomeInfraredProxy,
    state_type=EntityState,
)
