"""Set up the Elke27 integration."""

import contextlib
import logging

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import CONF_LINK_KEYS_JSON
from .coordinator import Elke27DataUpdateCoordinator
from .hub import Elke27Hub
from .models import Elke27ConfigEntry, Elke27RuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data[CONF_LINK_KEYS_JSON]
    client_id = entry.data[CONF_CLIENT_ID]
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
        raise ConfigEntryAuthFailed(msg) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.warning("Failed to set up connection to %s:%s: %s", host, port, err)
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        msg = "Unable to connect to the panel; check host and port"
        raise ConfigEntryNotReady(msg) from err

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    try:
        await coordinator.async_start()
        await coordinator.async_refresh_now()
    except (
        Elke27ConnectionError,
        Elke27TimeoutError,
        Elke27DisconnectedError,
        HomeAssistantError,
    ) as err:
        _LOGGER.warning(
            "Failed to refresh initial data from %s:%s: %s", host, port, err
        )
        with contextlib.suppress(Exception):
            await coordinator.async_stop()
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        msg = "Unable to refresh initial panel data"
        raise ConfigEntryNotReady(msg) from err

    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        with contextlib.suppress(Exception):
            await entry.runtime_data.coordinator.async_stop()
        with contextlib.suppress(Exception):
            await entry.runtime_data.hub.async_disconnect()
    return unload_ok
