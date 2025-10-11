"""Alexa Devices integration."""

from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import _LOGGER, CONF_LOGIN_DATA, CONF_SITE, COUNTRY_DOMAINS, DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alexa Devices component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Set up Alexa Devices platform."""

    session = aiohttp_client.async_create_clientsession(hass)
    coordinator = AmazonDevicesCoordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 3:
        if CONF_SITE in entry.data:
            # Site in data (wrong place), just move to login data
            new_data = entry.data.copy()
            new_data[CONF_LOGIN_DATA][CONF_SITE] = new_data[CONF_SITE]
            new_data.pop(CONF_SITE)
            hass.config_entries.async_update_entry(
                entry, data=new_data, version=1, minor_version=3
            )
            return True

        if CONF_SITE in entry.data[CONF_LOGIN_DATA]:
            # Site is there, just update version to avoid future migrations
            hass.config_entries.async_update_entry(entry, version=1, minor_version=3)
            return True

        _LOGGER.debug(
            "Migrating from version %s.%s", entry.version, entry.minor_version
        )

        # Convert country in domain
        country = entry.data[CONF_COUNTRY].lower()
        domain = COUNTRY_DOMAINS.get(country, country)

        # Add site to login data
        new_data = entry.data.copy()
        new_data[CONF_LOGIN_DATA][CONF_SITE] = f"https://www.amazon.{domain}"

        hass.config_entries.async_update_entry(
            entry, data=new_data, version=1, minor_version=3
        )

        _LOGGER.info(
            "Migration to version %s.%s successful", entry.version, entry.minor_version
        )

    # Handle customer ID migration for aioamazondevices 6.4.0 compatibility
    if entry.version == 1 and entry.minor_version < 4:
        from .utils import get_fallback_user_id
        
        login_data = entry.data.get(CONF_LOGIN_DATA, {})
        if not login_data.get("customer_info", {}).get("user_id"):
            fallback_user_id = get_fallback_user_id(
                entry.data[CONF_USERNAME], 
                login_data
            )
            new_data = entry.data.copy()
            new_data[CONF_LOGIN_DATA] = login_data.copy()
            new_data[CONF_LOGIN_DATA]["customer_info"] = {"user_id": fallback_user_id}
            
            hass.config_entries.async_update_entry(
                entry, data=new_data, version=1, minor_version=4
            )
            _LOGGER.info(
                "Migrated customer_info for aioamazondevices 6.4.0 compatibility"
            )
            return True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
