"""The Debug console integration, running Python inside Home Assistant."""

from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, IS_DEVELOPMENT_VERSION
from .safeguards import async_follow_removed_users
from .session import DebugConsoleConfigEntry, async_close_sessions
from .websocket_api import async_register_websocket_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Debug console.

    The console is enabled by its config entry. Development and nightly
    versions create that entry once, so it is on by default there, but stays
    off once removed.
    """
    async_register_websocket_commands(hass)

    if IS_DEVELOPMENT_VERSION:
        store = Store[dict[str, bool]](hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        if not data.get("enabled_automatically"):
            await store.async_save({"enabled_automatically": True})
            discovery_flow.async_create_flow(
                hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: DebugConsoleConfigEntry
) -> bool:
    """Enable the Debug console."""
    entry.runtime_data = {}
    await async_follow_removed_users(hass, entry)

    # Integrations are not unloaded on shutdown, but code still running in
    # the console should stop then too.
    async def _async_close_sessions(_event: Event) -> None:
        await async_close_sessions(entry.runtime_data)

    # Not async_listen_once: it fires only once anyway, and removing a listener
    # that fired fails on unload.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_close_sessions)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DebugConsoleConfigEntry
) -> bool:
    """Disable the Debug console."""
    await async_close_sessions(entry.runtime_data)
    return True
