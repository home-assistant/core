"""Support for Elgato Lights."""
from typing import NamedTuple

from elgato import Elgato, ElgatoConnectionError, Info, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

PLATFORMS = [Platform.BUTTON, Platform.LIGHT]


class HomeAssistantElgatoData(NamedTuple):
    """Elgato data stored in the Home Assistant data object."""

    coordinator: DataUpdateCoordinator[State]
    client: Elgato
    info: Info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elgato Light from a config entry."""
    session = async_get_clientsession(hass)
    elgato = Elgato(
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        session=session,
    )

    async def _async_update_data() -> State:
        """Fetch Elgato data."""
        try:
            return await elgato.state()
        except ElgatoConnectionError as err:
            raise UpdateFailed(err) from err

    coordinator: DataUpdateCoordinator[State] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
        update_interval=SCAN_INTERVAL,
        update_method=_async_update_data,
    )
    await coordinator.async_config_entry_first_refresh()

    info = await elgato.info()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantElgatoData(
        client=elgato,
        coordinator=coordinator,
        info=info,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Elgato Light config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
