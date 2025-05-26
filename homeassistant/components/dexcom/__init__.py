"""The Dexcom integration."""

from pydexcom import AccountError, Dexcom, SessionError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERVER, PLATFORMS, SERVER_OUS
from .coordinator import DexcomConfigEntry, DexcomCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DexcomConfigEntry) -> bool:
    """Set up Dexcom from a config entry."""
    try:
        dexcom = await hass.async_add_executor_job(
            Dexcom,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_SERVER] == SERVER_OUS,
        )
    except AccountError:
        return False
    except SessionError as error:
        raise ConfigEntryNotReady from error

    coordinator = DexcomCoordinator(hass, entry=entry, dexcom=dexcom)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DexcomConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
