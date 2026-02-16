"""The free_mobile component."""

from __future__ import annotations

from freesms import FreeClient

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

PLATFORMS = [Platform.NOTIFY]


type FreeMobileConfigEntry = ConfigEntry[FreeClient]


async def async_setup_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Set up Free Mobile from a config entry."""
    client = FreeClient(entry.data[CONF_USERNAME], entry.data[CONF_ACCESS_TOKEN])

    if entry.state is not ConfigEntryState.LOADED:
        try:
            await hass.async_add_executor_job(client.send_sms, "Home Assistant test")
        except Exception as err:
            if (
                "403" in str(err)
                or "Unauthorized" in str(err)
                or "authentication" in str(err).lower()
            ):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise ConfigEntryNotReady(
                f"Failed to connect to Free Mobile: {err}"
            ) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
