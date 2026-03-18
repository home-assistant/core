"""The Qube Heat Pump integration."""

from __future__ import annotations

from dataclasses import dataclass

from python_qube_heatpump import QubeClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import QubeCoordinator


@dataclass
class QubeData:
    """Runtime data for Qube Heat Pump."""

    coordinator: QubeCoordinator
    client: QubeClient
    sw_version: str | None


type QubeConfigEntry = ConfigEntry[QubeData]


async def async_setup_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Set up Qube Heat Pump from a config entry."""
    client = QubeClient(entry.data[CONF_HOST], entry.data[CONF_PORT])

    # Read software version for device info (best-effort, not critical)
    sw_version: str | None = None
    try:
        await client.connect()
        sw_version = await client.async_get_software_version()
    except OSError, TimeoutError:
        pass  # Version will be None; coordinator retry handles connectivity

    coordinator = QubeCoordinator(hass, client, entry)

    entry.runtime_data = QubeData(
        coordinator=coordinator,
        client=client,
        sw_version=sw_version,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QubeConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.client.close()
    return unload_ok
