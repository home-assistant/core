"""The Arris TG2492LG integration."""

from aiohttp import ClientConnectionError, ClientResponseError
from arris_tg2492lg import ConnectBox
from arris_tg2492lg.exception import InvalidCredentialError

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import ArrisConfigEntry, ArrisCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ArrisConfigEntry) -> bool:
    """Set up Arris TG2492LG from a config entry."""
    connect_box = ConnectBox(
        async_get_clientsession(hass),
        f"http://{entry.data[CONF_HOST]}",
        entry.data[CONF_PASSWORD],
    )

    try:
        await connect_box.async_login()
    except ClientConnectionError as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to router at {entry.data[CONF_HOST]}"
        ) from err
    except InvalidCredentialError as err:
        raise ConfigEntryAuthFailed("Invalid credentials for router") from err
    except ClientResponseError as err:
        if err.status == 401:
            raise ConfigEntryAuthFailed("Invalid credentials for router") from err
        raise ConfigEntryNotReady(
            f"Cannot connect to router at {entry.data[CONF_HOST]}"
        ) from err

    coordinator = ArrisCoordinator(hass, entry, connect_box)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArrisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
