"""The xiaomi component."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import XiaomiConfigEntry, XiaomiCoordinator
from .router import (
    XiaomiAuthError,
    XiaomiClient,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)


async def async_setup_entry(hass: HomeAssistant, entry: XiaomiConfigEntry) -> bool:
    """Set up Xiaomi from a config entry."""
    client = XiaomiClient(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        await hass.async_add_executor_job(client.login)
    except XiaomiTimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timed out connecting to router at {entry.data[CONF_HOST]}"
        ) from err
    except XiaomiConnectionError as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to router at {entry.data[CONF_HOST]}"
        ) from err
    except XiaomiAuthError as err:
        raise ConfigEntryAuthFailed("Invalid credentials for router") from err

    coordinator = XiaomiCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: XiaomiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
