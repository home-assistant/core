"""Nanoleaf util."""
from __future__ import annotations

import logging

from homeassistant.components import network
from homeassistant.components.network.models import Adapter
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .aionanoleaf import Nanoleaf

_LOGGER = logging.getLogger(__name__)


async def get_local_ip(
    hass: HomeAssistant, entry: ConfigEntry, nanoleaf: Nanoleaf
) -> str:
    """Return the Home Assistant local_ip for the Nanoleaf UDP socket."""
    adapters = await network.async_get_adapters(hass)
    local_ip: str | None = None
    adapter_ip: tuple[str, str] | None = entry.options.get("adapter_ip")

    if adapter_ip is None:
        # If no adapter and IP are configured use the default enabled adapter
        adapter_name, local_ip = await default_adapter_name_and_ip(adapters)
        if not network.async_only_default_interface_enabled(adapters):
            # Warn users with a manual network configuration, the user should set an adapter and IP in the entry option
            _LOGGER.warning(
                "No adapter selected, using adapter %s with IP %s for %s touch UDP socket",
                adapter_name,
                local_ip,
                nanoleaf.name,
            )
    else:
        # Check if the configured adapter still exists
        # Users using the default network configuration
        configured_adapter, configured_ip = adapter_ip
        local_ip = None
        for adapter in adapters:
            if adapter["name"] == configured_adapter:
                for ip in adapter["ipv4"]:
                    if ip["address"] == configured_ip:
                        # Configured adapter and IP still exist
                        return configured_ip
                # Adapter exists but IP is wrong, fallback to ip
                local_ip = adapter["ipv4"][0]["address"]
                _LOGGER.warning(
                    "Could not find configured IP %s on adapter %s, falling back to IP %s for %s",
                    configured_ip,
                    configured_adapter,
                    local_ip,
                    nanoleaf.name,
                )
            if local_ip is not None:
                break
        if local_ip is None:
            # Configured adapter does not exist anymore, fallback to default adapter and IP
            adapter_name, local_ip = await default_adapter_name_and_ip(adapters)
            _LOGGER.warning(
                "Could not find adapter %s, falling back to IP %s on adapter %s for %s",
                configured_ip,
                configured_adapter,
                local_ip,
                adapter_name,
                nanoleaf.name,
            )
    return local_ip


async def default_adapter_name_and_ip(adapters: list[Adapter]) -> tuple[str, str]:
    """Return default adapter name and ip."""
    for adapter in adapters:
        if adapter["enabled"] and adapter["default"]:
            return (adapter["name"], adapter["ipv4"][0]["address"])
    raise ValueError(
        "Couldn't find default adapter, set an adapter in the Nanoleaf configuration"
    )
