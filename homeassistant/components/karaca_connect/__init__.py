"""Karaca Connect integration for Home Assistant."""

from dataclasses import dataclass

from karaca_connect_client import KaracaAuthError, KaracaClient, KaracaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, PLATFORMS
from .coordinator import KaracaCoordinator


@dataclass
class KaracaRuntimeData:
    """Runtime data for one configured Karaca device."""

    client: KaracaClient
    coordinator: KaracaCoordinator


type KaracaConfigEntry = ConfigEntry[KaracaRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: KaracaConfigEntry) -> None:
    """Set up a Karaca device from a config entry."""
    client = KaracaClient(
        async_get_clientsession(hass),
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        device_id=entry.data[CONF_DEVICE_ID],
    )
    try:
        await client.login()
    except KaracaAuthError as exc:
        raise ConfigEntryAuthFailed("Cannot authenticate with Karaca Connect") from exc
    except KaracaError as exc:
        raise ConfigEntryNotReady("Karaca Connect service is unavailable") from exc
    coordinator = KaracaCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = KaracaRuntimeData(client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: KaracaConfigEntry) -> None:
    """Unload the integration platforms."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
