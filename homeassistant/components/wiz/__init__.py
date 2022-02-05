"""WiZ Platform integration."""
from datetime import timedelta
import logging

from pywizlight import wizlight

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, WIZ_EXCEPTIONS
from .models import WizData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the wiz integration from a config entry."""
    ip_address = entry.data[CONF_HOST]
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    bulb = wizlight(ip_address)
    try:
        scenes = await bulb.getSupportedScenes()
        await bulb.getMac()
    except WIZ_EXCEPTIONS as err:
        raise ConfigEntryNotReady from err

    async def _async_update() -> None:
        """Update the WiZ device."""
        try:
            await bulb.updateState()
        except WIZ_EXCEPTIONS as ex:
            raise UpdateFailed(f"Failed to update device at {ip_address}: {ex}") from ex

    coordinator = DataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        name=entry.data[CONF_NAME],
        update_interval=timedelta(seconds=15),
        update_method=_async_update,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WizData(
        coordinator=coordinator, bulb=bulb, scenes=scenes
    )
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
