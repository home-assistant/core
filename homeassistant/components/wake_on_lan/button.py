"""Support for button entity in wake on lan."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

import wakeonlan

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wake on LAN button entry."""
    broadcast_address: str | None = entry.options.get(CONF_BROADCAST_ADDRESS)
    broadcast_port: int | None = entry.options.get(CONF_BROADCAST_PORT)
    mac_address: str = entry.options[CONF_MAC]
    name: str = entry.title

    async_add_entities(
        [
            WolButton(
                name,
                mac_address,
                broadcast_address,
                broadcast_port,
            )
        ]
    )


class WolButton(ButtonEntity):
    """Representation of a wake on lan button."""

    _attr_name = None

    def __init__(
        self,
        name: str,
        mac_address: str,
        broadcast_address: str | None,
        broadcast_port: int | None,
    ) -> None:
        """Initialize the WOL button."""
        self._mac_address = mac_address
        self._broadcast_address = broadcast_address
        self._broadcast_port = broadcast_port
        self._attr_unique_id = dr.format_mac(mac_address)
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._attr_unique_id)},
            default_manufacturer="Wake on LAN",
            default_name=name,
        )

    async def async_press(self) -> None:
        """Press the button."""
        service_kwargs: dict[str, Any] = {}
        if self._broadcast_address is not None:
            service_kwargs["ip_address"] = self._broadcast_address
        if self._broadcast_port is not None:
            service_kwargs["port"] = self._broadcast_port

        _LOGGER.debug(
            "Send magic packet to mac %s (broadcast: %s, port: %s)",
            self._mac_address,
            self._broadcast_address,
            self._broadcast_port,
        )

        await self.hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, self._mac_address, **service_kwargs)
        )
