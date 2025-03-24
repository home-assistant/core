"""Support for wake on lan."""

from __future__ import annotations

import logging
import subprocess as sp
from typing import Any

import wakeonlan

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.script import Script

from .const import CONF_OFF_ACTION, DEFAULT_PING_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Wake on LAN switch entry."""
    broadcast_address: str | None = entry.options.get(CONF_BROADCAST_ADDRESS)
    broadcast_port: int | None = entry.options.get(CONF_BROADCAST_PORT)
    host: str | None = entry.options.get(CONF_HOST)
    mac_address: str = entry.options[CONF_MAC]
    name: str = entry.title
    off_action: list[Any] | None = entry.options.get(CONF_OFF_ACTION)

    async_add_entities(
        [
            WolSwitch(
                hass,
                name,
                host,
                mac_address,
                off_action,
                broadcast_address,
                broadcast_port,
            )
        ],
        host is not None,
    )


class WolSwitch(SwitchEntity):
    """Representation of a wake on lan switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str | None,
        mac_address: str,
        off_action: list[Any] | None,
        broadcast_address: str | None,
        broadcast_port: int | None,
    ) -> None:
        """Initialize the WOL switch."""
        self._attr_name = name
        self._host = host
        self._mac_address = mac_address
        self._broadcast_address = broadcast_address
        self._broadcast_port = broadcast_port
        self._off_script = (
            Script(hass, off_action, name, DOMAIN) if off_action else None
        )
        self._state = False
        self._attr_assumed_state = host is None
        self._attr_should_poll = bool(not self._attr_assumed_state)
        self._attr_unique_id = dr.format_mac(mac_address)
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._attr_unique_id)},
            default_name=name,
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
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

        wakeonlan.send_magic_packet(self._mac_address, **service_kwargs)

        if self._attr_assumed_state:
            self._state = True
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off if an off action is present."""
        if self._off_script is not None:
            self._off_script.run(context=self._context)

        if self._attr_assumed_state:
            self._state = False
            self.schedule_update_ha_state()

    def update(self) -> None:
        """Check if device is on and update the state. Only called if assumed state is false."""
        ping_cmd = [
            "ping",
            "-c",
            "1",
            "-W",
            str(DEFAULT_PING_TIMEOUT),
            str(self._host),
        ]

        status = sp.call(ping_cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        self._state = not bool(status)
