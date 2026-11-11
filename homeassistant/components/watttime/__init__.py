"""The WattTime integration."""

from aiowatttime import Client
from aiowatttime.errors import InvalidCredentialsError, WattTimeError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .coordinator import WattTimeConfigEntry, WattTimeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WattTimeConfigEntry) -> None:
    """Set up WattTime from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await Client.async_login(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username/password") from err
    except WattTimeError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from err

    coordinator = WattTimeCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))


async def async_unload_entry(hass: HomeAssistant, entry: WattTimeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, config_entry: WattTimeConfigEntry
) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
