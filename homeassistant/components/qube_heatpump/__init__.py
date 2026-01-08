"""The Qube Heat Pump integration."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration, async_get_loaded_integration

from .const import CONF_HOST, CONF_PORT, CONF_UNIT_ID, DEFAULT_PORT, DOMAIN, PLATFORMS
from .coordinator import QubeCoordinator
from .hub import QubeHub


@dataclass
class QubeData:
    """Runtime data for Qube Heat Pump."""

    hub: QubeHub
    coordinator: QubeCoordinator
    version: str
    tariff_tracker: Any | None = None
    thermic_tariff_tracker: Any | None = None
    daily_tariff_tracker: Any | None = None
    daily_thermic_tariff_tracker: Any | None = None


type QubeConfigEntry = ConfigEntry[QubeData]

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Make text safe for use as an ID."""
    return "".join(ch if ch.isalnum() else "_" for ch in str(text)).strip("_").lower()


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

    entry.runtime_data = QubeData(
        hub=hub,
        coordinator=coordinator,
        version=version,
    )

    with contextlib.suppress(Exception):
        ir.async_delete_issue(hass, DOMAIN, "registry_migration_suggested")

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
