"""Set up ohme integration."""

import logging

from ohme import ApiException, AuthException, OhmeApiClient

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    OhmeChargeSessionCoordinator,
    OhmeConfigEntry,
    OhmeDeviceInfoCoordinator,
    OhmeRuntimeData,
)
from .history import async_ensure_energy_history, async_remove_energy_history
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Ohme integration."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Set up Ohme from a config entry."""

    client = OhmeApiClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    try:
        await client.async_login()

        if not await client.async_update_device_info():
            raise ConfigEntryNotReady(
                translation_key="device_info_failed", translation_domain=DOMAIN
            )
    except AuthException as e:
        raise ConfigEntryAuthFailed(
            translation_key="auth_failed", translation_domain=DOMAIN
        ) from e
    except ApiException as e:
        raise ConfigEntryNotReady(
            translation_key="api_failed", translation_domain=DOMAIN
        ) from e

    charge_session_coordinator = OhmeChargeSessionCoordinator(hass, entry, client)
    device_info_coordinator = OhmeDeviceInfoCoordinator(hass, entry, client)

    if entry.unique_id != client.serial:
        hass.config_entries.async_update_entry(entry, unique_id=client.serial)

    entry.runtime_data = OhmeRuntimeData(
        charge_session_coordinator=charge_session_coordinator,
        device_info_coordinator=device_info_coordinator,
    )

    for coordinator in (charge_session_coordinator, device_info_coordinator):
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    try:
        result = await async_ensure_energy_history(hass, entry)
    except Exception:
        _LOGGER.exception("Failed to initialize Ohme energy history sync")
    else:
        _LOGGER.debug("Initialized Ohme energy history sync: %s", result)

    charge_session_coordinator.seed_history_sync_state()
    charge_session_coordinator.enable_history_sync()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.charge_session_coordinator.disable_history_sync()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: OhmeConfigEntry) -> None:
    """Remove a config entry and its imported recorder history."""
    try:
        await async_remove_energy_history(hass, entry)
    except Exception:
        _LOGGER.exception("Failed to remove Ohme energy history")
