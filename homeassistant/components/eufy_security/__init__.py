"""The Eufy Security integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnectError,
    EufySecurityError,
    InvalidCredentialsError,
    async_login,
)
from .const import DOMAIN, PLATFORMS
from .coordinator import (
    EufySecurityConfigEntry,
    EufySecurityCoordinator,
    EufySecurityData,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Set up Eufy Security from a config entry."""
    session = async_get_clientsession(hass)

    try:
        api = await async_login(
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
            session,
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except CannotConnectError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except EufySecurityError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    coordinator = EufySecurityCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = EufySecurityData(
        api=api,
        devices={
            "cameras": {camera.serial: camera for camera in api.cameras.values()},
            "stations": {station.serial: station for station in api.stations.values()},
        },
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EufySecurityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
