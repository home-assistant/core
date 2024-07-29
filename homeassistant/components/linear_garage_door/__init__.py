"""The Nice G.O. integration."""

from __future__ import annotations

from datetime import datetime
import logging

from nice_go import ApiError, AuthFailedError, NiceGOApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_ID,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    CONF_SITE_ID,
    DOMAIN,
)
from .coordinator import NiceGOUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.COVER, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nice G.O. from a config entry."""

    coordinator = NiceGOUpdateCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.client_listen(),
        "nice_go_websocket_task",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.api.close()

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    # Migrate version 1 -> 2: Migrate from old API to new API
    if entry.version < 2:
        new_data = {**entry.data}

        # These are no longer used with the new API
        new_data.pop(CONF_SITE_ID, None)
        new_data.pop(CONF_DEVICE_ID, None)

        # Try to get the refresh token from the old email and password
        api = NiceGOApi()
        session = async_get_clientsession(hass)

        try:
            refresh_token = await api.authenticate(
                new_data[CONF_EMAIL], new_data[CONF_PASSWORD], session=session
            )
        except AuthFailedError as e:
            _LOGGER.error("Authentication failed during migration: %s", e)
            return False
        except ApiError as e:
            _LOGGER.error("API error during migration: %s", e)
            if "UserNotFoundException" in str(e.__context__):
                # Since it (probably) was working before, we can assume that the
                # credentials are correct, but the user hasn't migrated their
                # account yet.

                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    f"account_migration_required_{DOMAIN}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="account_migration_required",
                )
            return False

        # Remove the issue if it exists
        ir.async_delete_issue(hass, DOMAIN, "account_migration_required")

        new_data[CONF_REFRESH_TOKEN] = refresh_token
        new_data[CONF_REFRESH_TOKEN_CREATION_TIME] = datetime.now().timestamp()

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=1,
            version=2,
            unique_id=new_data[CONF_EMAIL],
        )

    _LOGGER.debug("Migration to version %s completed", entry.version)

    return True
