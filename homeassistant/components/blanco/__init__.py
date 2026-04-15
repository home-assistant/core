"""The blanco integration."""

from __future__ import annotations

import contextlib
import logging

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoConnectionError,
    BlancoLogLevel,
    blanco_log,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    Platform,
    __version__ as HA_VERSION,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_TOKEN,
    CONF_TOKEN_TYPE,
    DOMAIN,
)
from .coordinator import BlancoDataUpdateCoordinator
from .migration import migrate_entity_ids, migrate_sensor_units, migrate_statistic_ids

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type BlancoConfigEntry = ConfigEntry[BlancoDataUpdateCoordinator]
"""Type alias for a config entry whose runtime_data is the coordinator."""


async def _async_ensure_app_registered(
    hass: HomeAssistant, entry: BlancoConfigEntry
) -> str:
    """Return the stored app_id, registering with the API if not yet done."""
    if app_id := entry.data.get(CONF_APP_ID):
        return app_id

    locale = hass.config.language.split("-")[0][:2]
    session = async_get_clientsession(hass)
    client = BlancoApiClient(session, os_version=HA_VERSION)
    try:
        reg = await client.register_app(locale)
    except BlancoConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_APP_ID: reg["app_id"], CONF_APP_LOCALE: locale},
    )
    return reg["app_id"]


async def _async_setup_language_listener(
    hass: HomeAssistant, entry: BlancoConfigEntry
) -> None:
    """Listen for HA language changes and notify the BLANCO API via PUT."""

    async def _handle_core_config_update(event: Event) -> None:
        """Update the app locale on the BLANCO API when HA language changes."""
        if "language" not in event.data:
            return

        app_id = entry.data.get(CONF_APP_ID)
        if not app_id:
            return

        new_locale = hass.config.language.split("-")[0][:2]
        if new_locale == entry.data.get(CONF_APP_LOCALE):
            return

        session = async_get_clientsession(hass)
        client = BlancoApiClient(session, app_id=app_id, os_version=HA_VERSION)
        try:
            success = await client.update_app_locale(new_locale)
        except BlancoConnectionError:
            return  # failure already logged in api.py
        if success:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_APP_LOCALE: new_locale}
            )

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _handle_core_config_update)
    )


async def async_setup_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Set up blanco from a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    build = integration.manifest.get("build")
    version: str = str(integration.version or "")
    version_str: str = (
        f"{version} ({build})" if (version and build is not None) else (version or "—")
    )
    blanco_log(
        _LOGGER,
        BlancoLogLevel.INFO,
        "Starting %s v%s",
        integration.name,
        version_str,
    )

    migrate_sensor_units(hass, entry.entry_id)
    migrate_entity_ids(
        hass,
        entry.entry_id,
        dev_id=entry.data.get(CONF_DEV_ID, ""),
        serial=entry.data.get(CONF_SERIAL, ""),
    )
    migrate_statistic_ids(hass, entry.entry_id)
    app_id = await _async_ensure_app_registered(hass, entry)
    await _async_setup_language_listener(hass, entry)
    coordinator = BlancoDataUpdateCoordinator(
        hass,
        entry=entry,
        token=entry.data[CONF_TOKEN],
        token_type=entry.data.get(CONF_TOKEN_TYPE, "Bearer"),
        dev_id=entry.data[CONF_DEV_ID],
        dev_type=entry.data.get(CONF_DEV_TYPE),
        serial=entry.data[CONF_SERIAL],
        app_id=app_id,
        app_version=str(integration.version or ""),
        app_build=str(build or ""),
    )
    await coordinator.async_config_entry_first_refresh()
    dev_name = coordinator.data.get("system", {}).get("params", {}).get("dev_name")
    if dev_name and entry.title != dev_name:
        hass.config_entries.async_update_entry(entry, title=dev_name)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: BlancoConfigEntry) -> None:
    """Deregister the app from the BLANCO API when the integration is removed."""
    app_id = entry.data.get(CONF_APP_ID)
    token = entry.data.get(CONF_TOKEN)
    token_type = entry.data.get(CONF_TOKEN_TYPE, "Bearer")

    if not app_id or not token:
        return

    session = async_get_clientsession(hass)
    client = BlancoApiClient(
        session,
        app_id=app_id,
        token=str(token),
        token_type=str(token_type),
        os_version=HA_VERSION,
    )
    with contextlib.suppress(BlancoConnectionError):
        await client.deregister_app()
