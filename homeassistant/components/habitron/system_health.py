"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


def _aggregate_router_status(hubs: list[Any]) -> str:
    """Return aggregate router health across all configured SmartHubs."""
    if not hubs:
        return "no hubs"
    if all(hub.router.sys_ok for hub in hubs):
        return "ok"
    return "errors"


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    hubs = [
        entry.runtime_data for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ]
    integration = await async_get_integration(hass, DOMAIN)
    return {
        "hbtn_version": str(integration.version) if integration.version else "0.0.0",
        "hub_count": len(hubs),
        "router_status": _aggregate_router_status(hubs),
        "module_count": sum(len(hub.router.modules) for hub in hubs),
    }
