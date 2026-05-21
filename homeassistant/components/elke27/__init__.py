"""Set up the Elke27 integration."""

import contextlib
import logging
from typing import TYPE_CHECKING

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_CLIENT_ID, CONF_LINK_KEYS_JSON, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .hub import Elke27Hub
from .models import Elke27ConfigEntry, Elke27RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup(_hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Elke27 integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data.get(CONF_LINK_KEYS_JSON)
    if not link_keys_json:
        msg = "Link keys are missing"
        raise ConfigEntryError(msg)
    client_id = entry.data.get(CONF_CLIENT_ID)
    if not client_id:
        msg = "Client ID is missing"
        raise ConfigEntryError(msg)
    hub = Elke27Hub(
        hass,
        host,
        port,
        link_keys_json,
        client_id,
        None,
    )
    try:
        await hub.async_connect()
    except Elke27LinkRequiredError as err:
        msg = "Linking credentials are invalid"
        raise ConfigEntryError(msg) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.exception("Failed to set up connection to %s:%s", host, port)
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        msg = "The client did not become ready; check host and port"
        raise ConfigEntryNotReady(msg) from err

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    await coordinator.async_start()
    await coordinator.async_refresh_now()

    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_stop()
        await entry.runtime_data.hub.async_disconnect()
    return unload_ok
