"""The Remootio integration."""

from pyremootio import (
    RemootioAuthenticationError,
    RemootioClient,
    RemootioConnectionError,
    RemootioCryptoError,
    RemootioTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY

_PLATFORMS: list[Platform] = [Platform.COVER]

type RemootioConfigEntry = ConfigEntry[RemootioClient]


async def async_setup_entry(hass: HomeAssistant, entry: RemootioConfigEntry) -> bool:
    """Set up Remootio from a config entry."""
    try:
        client = RemootioClient(
            entry.data[CONF_HOST],
            entry.data[CONF_API_SECRET_KEY],
            entry.data[CONF_API_AUTH_KEY],
            async_get_clientsession(hass),
        )
    except ValueError as err:
        raise ConfigEntryAuthFailed from err

    try:
        await client.connect()
    except (RemootioAuthenticationError, RemootioCryptoError) as err:
        await client.disconnect()
        raise ConfigEntryAuthFailed from err
    except (RemootioConnectionError, RemootioTimeoutError) as err:
        await client.disconnect()
        raise ConfigEntryNotReady from err

    @callback
    def _async_on_auth_failure() -> None:
        entry.async_start_reauth(hass)

    entry.async_on_unload(client.listen_auth_failure(_async_on_auth_failure))
    client.enable_reconnect()

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemootioConfigEntry) -> bool:
    """Unload a config entry and close the websocket."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok
