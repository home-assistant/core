"""The Schlage integration."""

from __future__ import annotations

from pycognito.exceptions import WarrantException
import pyschlage
import voluptuous as vol

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, SERVICE_ADD_CODE, SERVICE_DELETE_CODE, SERVICE_GET_CODES
from .coordinator import SchlageConfigEntry, SchlageDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Schlage component."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required("name"): cv.string,
            vol.Required("code"): cv.matches_regex(r"^\d{4,8}$"),
        },
        func=SERVICE_ADD_CODE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_CODE,
        entity_domain=LOCK_DOMAIN,
        schema={
            vol.Required("name"): cv.string,
        },
        func=SERVICE_DELETE_CODE,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_CODES,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func=SERVICE_GET_CODES,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SchlageConfigEntry) -> bool:
    """Set up Schlage from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    try:
        auth = await hass.async_add_executor_job(pyschlage.Auth, username, password)
    except WarrantException as ex:
        raise ConfigEntryAuthFailed from ex

    coordinator = SchlageDataUpdateCoordinator(
        hass, entry, username, pyschlage.Schlage(auth)
    )
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SchlageConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
