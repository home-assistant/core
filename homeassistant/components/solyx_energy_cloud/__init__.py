"""Solyx Energy integration."""

from solyx_energy_api.client import SolyxEnergyApiClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL, CONF_NYMO_CLIENT_ID, CONF_NYMO_CLIENT_SECRET, REALM_ID
from .coordinator import SolyxEnergyConfigEntry, SolyxEnergyCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolyxEnergyConfigEntry) -> None:
    """Init function upon Solyx Energy account setup from a config entry."""
    session = async_get_clientsession(hass)
    api_client = SolyxEnergyApiClient(
        session=session,
        nymo_client_id=entry.data[CONF_NYMO_CLIENT_ID],
        nymo_client_secret=entry.data[CONF_NYMO_CLIENT_SECRET],
        base_url=BASE_URL,
        realm_id=REALM_ID,
    )
    coordinator = SolyxEnergyCoordinator(
        hass=hass,
        api_client=api_client,
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
