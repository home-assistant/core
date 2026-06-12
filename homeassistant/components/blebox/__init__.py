"""The BleBox devices integration."""

from blebox_uniapi.box import Box
from blebox_uniapi.error import ConnectionError, Error, HttpError, UnauthorizedRequest
from blebox_uniapi.session import ApiHost

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import DEFAULT_SETUP_TIMEOUT
from .coordinator import BleBoxConfigEntry, BleBoxCoordinator
from .helpers import get_maybe_authenticated_session

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: BleBoxConfigEntry) -> bool:
    """Set up BleBox devices from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    timeout = DEFAULT_SETUP_TIMEOUT

    websession = get_maybe_authenticated_session(hass, password, username)

    api_host = ApiHost(host, port, timeout, websession, hass.loop)

    try:
        product = await Box.async_from_host(api_host)
    except UnauthorizedRequest as ex:
        raise ConfigEntryAuthFailed from ex
    except (
        ConnectionError,
        HttpError,
    ) as ex:
        raise ConfigEntryNotReady from ex
    except Error as ex:
        raise ConfigEntryError from ex

    coordinator = BleBoxCoordinator(hass, entry, product)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BleBoxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
