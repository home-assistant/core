"""The Qube Heat Pump integration."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.loader import async_get_integration, async_get_loaded_integration

from .const import CONF_UNIT_ID, DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import QubeCoordinator
from .hub import QubeHub


@dataclass
class QubeData:
    """Runtime data for Qube Heat Pump."""

    hub: QubeHub
    coordinator: QubeCoordinator
    version: str
    device_name: str


type QubeConfigEntry = ConfigEntry[QubeData]

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Set up Qube Heat Pump from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    unit_id = int(entry.data.get(CONF_UNIT_ID, 1))

    # Support unit_id from options if present (migration path or legacy)
    # But generally we should prefer data.
    if CONF_UNIT_ID in entry.options:
        unit_id = int(entry.options[CONF_UNIT_ID])

    # Construct a label for the hub mainly for debug/logs, not for entity naming
    label = f"{host}:{unit_id}"

    hub = QubeHub(hass, host, port, entry.entry_id, unit_id, label)
    await hub.async_resolve_ip()

    version = "unknown"
    with contextlib.suppress(Exception):
        integration = async_get_loaded_integration(hass, DOMAIN)
        if not integration:
            integration = await async_get_integration(hass, DOMAIN)
        if integration and getattr(integration, "version", None):
            version = str(integration.version)

    coordinator = QubeCoordinator(hass, hub, entry)

    # Use configured device name from CONF_NAME, fallback to entry title
    device_name = entry.data.get(CONF_NAME) or entry.title or "Qube Heat Pump"

    entry.runtime_data = QubeData(
        hub=hub,
        coordinator=coordinator,
        version=version,
        device_name=device_name,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Use contextlib.suppress to safely handle cleanup even if setup failed
    with contextlib.suppress(AttributeError):
        if hub := entry.runtime_data.hub:
            await hub.async_close()

    return bool(unload_ok)
