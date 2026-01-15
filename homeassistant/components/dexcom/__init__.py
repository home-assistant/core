"""The Dexcom integration."""

import logging

from pydexcom import Dexcom, Region
from pydexcom.errors import AccountError, ServerError, SessionError

from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import DexcomConfigEntry, DexcomCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DexcomConfigEntry) -> bool:
    """Set up Dexcom from a config entry."""
    try:
        dexcom = await hass.async_add_executor_job(
            lambda: Dexcom(
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                region=entry.data[CONF_REGION],
            )
        )
    except AccountError as error:
        raise ConfigEntryAuthFailed from error
    except (ServerError, SessionError) as error:
        _LOGGER.exception("Dexcom error")
        raise ConfigEntryNotReady from error

    coordinator = DexcomCoordinator(hass, entry=entry, dexcom=dexcom)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DexcomConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
