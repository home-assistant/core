"""The IntelliFire integration."""
from __future__ import annotations

from aiohttp import ClientConnectionError
from intellifire4py import IntellifireAsync, IntellifireControlAsync
from intellifire4py.control import LoginException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IntelliFire from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Define the API Objects
    read_object = IntellifireAsync(entry.data[CONF_HOST])

    ift_control = IntellifireControlAsync(
        fireplace_ip=entry.data[CONF_HOST],
        # use_http=(not entry.data[CONF_SSL]),
        # verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    try:
        await ift_control.login(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
    except (ConnectionError, ClientConnectionError, LoginException) as err:
        raise ConfigEntryAuthFailed(err) from err
    finally:
        await ift_control.close()

    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass, read_api=read_object, control_api=ift_control
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# Example migration function
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    version = config_entry.version

    if version == 1:

        # Version 1 doesn't have API information so we will replace username/password with dummy data and a reauth flow will get triggered above

        config_entry.version = 2
        new = {**config_entry.data}
        new[CONF_USERNAME] = "reauth_required"
        new[CONF_PASSWORD] = "not_set"
        hass.config_entries.async_update_entry(config_entry, data=new)

    LOGGER.info("Migration to version %s successful", config_entry.version)
    return True

    # print("MIGRATION:", new)
    # if config_entry.version == 1:

    #     new = {**config_entry.data}
    #     print("MIGRATION:", new)
    #     return await self.async_step_reauth()

    #     config_entry.version = 2
    #     hass.config_entries.async_update_entry(config_entry, data=new)

    # return True
