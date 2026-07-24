"""Solyx Energy integration."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolyxEnergyApiClient
from .const import CONF_NYMO_CLIENT_ID, CONF_NYMO_CLIENT_SECRET, CONF_NYMO_DEVICE_ID
from .coordinator import SolyxEnergyCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

type SolyxEnergyConfigEntry = ConfigEntry[SolyxEnergyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SolyxEnergyConfigEntry) -> bool:
    """Init function upon Solyx Energy device setup from a config entry."""
    session = async_get_clientsession(hass)
    api_client = SolyxEnergyApiClient(
        session=session,
        nymo_client_id=entry.data[CONF_NYMO_CLIENT_ID],
        nymo_client_secret=entry.data[CONF_NYMO_CLIENT_SECRET],
    )
    coordinator = SolyxEnergyCoordinator(
        hass=hass,
        api_client=api_client,
        device_id=entry.data[CONF_NYMO_DEVICE_ID],
        config_entry=entry,
    )
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
