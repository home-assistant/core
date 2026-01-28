"""The PulseGrow integration."""

from __future__ import annotations

from aiopulsegrow import PulsegrowClient, PulsegrowError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUFACTURER
from .coordinator import PulseGrowDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type PulseGrowConfigEntry = ConfigEntry[PulseGrowDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PulseGrowConfigEntry) -> bool:
    """Set up PulseGrow from a config entry."""
    client = PulsegrowClient(
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    # Validate connection
    try:
        await client.get_users()
    except PulsegrowError as err:
        raise ConfigEntryNotReady(f"Failed to connect to PulseGrow: {err}") from err

    coordinator = PulseGrowDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Register hub devices in device registry
    await _async_register_hub_devices(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_register_hub_devices(
    hass: HomeAssistant,
    entry: PulseGrowConfigEntry,
    coordinator: PulseGrowDataUpdateCoordinator,
) -> None:
    """Register hub devices in the device registry."""
    device_registry = dr.async_get(hass)

    for hub_id, hub in coordinator.data.hubs.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, hub_id)},
            name=hub.name,
            manufacturer=MANUFACTURER,
            model="PulseHub",
        )


async def async_unload_entry(hass: HomeAssistant, entry: PulseGrowConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
