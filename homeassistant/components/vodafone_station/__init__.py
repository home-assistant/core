"""Vodafone Station integration."""

from aiohttp import ClientSession, CookieJar
from aiovodafone.models import get_device_type

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER, CONF_DEVICE_DETAILS, DEVICE_TYPE, DEVICE_URL
from .coordinator import VodafoneConfigEntry, VodafoneStationRouter
from .utils import async_client_session

PLATFORMS = [Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VodafoneConfigEntry) -> bool:
    """Set up Vodafone Station platform."""
    session = await async_client_session(hass)
    coordinator = VodafoneStationRouter(
        hass,
        entry,
        session,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: VodafoneConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1 and entry.minor_version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s", entry.version, entry.minor_version
        )

        jar = CookieJar(unsafe=True, quote_cookie=False)
        session = ClientSession(cookie_jar=jar)

        try:
            device_type, url = await get_device_type(
                entry.data[CONF_HOST],
                session,
            )
        finally:
            await session.close()

        # Save device details to config entry
        new_data = entry.data.copy()
        new_data.update(
            {
                CONF_DEVICE_DETAILS: {
                    DEVICE_TYPE: device_type.value,
                    DEVICE_URL: str(url),
                }
            },
        )

        hass.config_entries.async_update_entry(
            entry, data=new_data, version=1, minor_version=2
        )

        _LOGGER.info(
            "Migration to version %s.%s successful", entry.version, entry.minor_version
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VodafoneConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.api.logout()

    return unload_ok
