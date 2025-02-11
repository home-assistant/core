"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from . import Adapter, async_get_adapters, async_get_announce_addresses
from .models import IPv4ConfiguredAddress, IPv6ConfiguredAddress


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/config/network")


def _format_ips(ips: list[IPv4ConfiguredAddress] | list[IPv6ConfiguredAddress]) -> str:
    return ", ".join([f"{ip['address']}/{ip['network_prefix']!s}" for ip in ips])


def _get_adapter_info(adapter: Adapter) -> str:
    state = "enabled" if adapter["enabled"] else "disabled"
    default = ", default" if adapter["default"] else ""
    auto = ", auto" if adapter["auto"] else ""
    return f"{adapter['name']} ({state}{default}{auto})"


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""

    adapters = await async_get_adapters(hass)
    data: dict[str, Any] = {
        # k: v for adapter in adapters for k, v in _get_adapter_info(adapter).items()
        "adapters": ", ".join([_get_adapter_info(adapter) for adapter in adapters]),
        "ipv4_addresses": ", ".join(
            [
                f"{adapter['name']} ({_format_ips(adapter['ipv4'])})"
                for adapter in adapters
            ]
        ),
        "ipv6_addresses": ", ".join(
            [
                f"{adapter['name']} ({_format_ips(adapter['ipv6'])})"
                for adapter in adapters
            ]
        ),
        "announce_addresses": ", ".join(await async_get_announce_addresses(hass)),
    }

    return data
