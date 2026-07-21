"""The Poolside integration."""

from base64 import b64decode
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .client import (
    PoolsideAuthError,
    PoolsideClient,
    PoolsideCommandError,
    PoolsideConnectionError,
)
from .const import (
    CONF_CLIENT_PRIVATE_KEY,
    CONF_CONTROLLER_PUBLIC_KEY,
    CONF_CONTROLLER_UUID,
)
from .models import PoolsideControl

PLATFORMS = [Platform.CLIMATE, Platform.FAN, Platform.LIGHT, Platform.SWITCH]


@dataclass
class PoolsideData:
    """Runtime data for a Poolside config entry."""

    client: PoolsideClient
    controls: list[PoolsideControl]


type PoolsideConfigEntry = ConfigEntry[PoolsideData]


async def async_setup_entry(hass: HomeAssistant, entry: PoolsideConfigEntry) -> bool:
    """Set up Poolside from a config entry."""
    client = PoolsideClient(
        session=aiohttp_client.async_get_clientsession(hass),
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        client_private_key=b64decode(entry.data[CONF_CLIENT_PRIVATE_KEY]),
        controller_public_key=b64decode(entry.data[CONF_CONTROLLER_PUBLIC_KEY]),
        controller_uuid=entry.data[CONF_CONTROLLER_UUID],
    )

    try:
        await client.async_connect()
    except PoolsideAuthError as err:
        raise ConfigEntryAuthFailed from err
    except PoolsideConnectionError as err:
        raise ConfigEntryNotReady from err

    client.set_auth_failure_callback(lambda: entry.async_start_reauth(hass))

    try:
        _site_name, controls = await client.async_get_control_layout()
    except (PoolsideConnectionError, PoolsideCommandError) as err:
        await client.async_disconnect()
        raise ConfigEntryNotReady from err

    entry.runtime_data = PoolsideData(client=client, controls=controls)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PoolsideConfigEntry) -> bool:
    """Unload a Poolside config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.client.async_disconnect()
    return unload_ok
