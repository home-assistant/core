"""Alexa Devices integration."""

import asyncio
import contextlib

from homeassistant.components.labs import (
    EventLabsUpdatedData,
    async_is_preview_feature_enabled,
    async_subscribe_preview_feature,
)
from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    entity_registry as er,
    httpx_client,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import _LOGGER, CONF_LOGIN_DATA, CONF_SITE, COUNTRY_DOMAINS, DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.MEDIA_PLAYER,
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

    non_labs_platforms = [p for p in PLATFORMS if p != Platform.MEDIA_PLAYER]

    session = aiohttp_client.async_create_clientsession(hass)
    coordinator = AmazonDevicesCoordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    await coordinator.sync_history_state()

    async def _on_http2_reauth_required() -> None:
        entry.async_start_reauth(hass)

    async def _cancel_http2() -> None:
        http2_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await http2_task

    alexa_httpx_client = httpx_client.get_async_client(
        hass,
        alpn_protocols=SSL_ALPN_HTTP11_HTTP2,
    )

    http2_task = await coordinator.api.start_http2_processing(
        alexa_httpx_client, on_reauth_required=_on_http2_reauth_required
    )

    entry.async_on_unload(_cancel_http2)

    media_player_loaded = False
    _update_lock = asyncio.Lock()

    def _async_set_media_player_registry(*, enabled: bool) -> None:
        """Sync media player registry entry disabled state with labs status."""
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

        for entity in entities:
            if entity.domain != Platform.MEDIA_PLAYER:
                continue

            if enabled and entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                ent_reg.async_update_entity(entity.entity_id, disabled_by=None)
            elif not enabled and entity.disabled_by is None:
                ent_reg.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )

    async def _async_update_alexa_media(
        event_data: EventLabsUpdatedData | None = None,
    ) -> None:
        nonlocal media_player_loaded

        async with _update_lock:
            enabled = (
                event_data["enabled"]
                if event_data is not None
                else async_is_preview_feature_enabled(hass, DOMAIN, "alexa_media")
            )

            if enabled:
                _async_set_media_player_registry(enabled=True)
                await coordinator.sync_media_state()

                if not media_player_loaded:
                    await hass.config_entries.async_forward_entry_setups(
                        entry, [Platform.MEDIA_PLAYER]
                    )
                    media_player_loaded = True
            else:
                _async_set_media_player_registry(enabled=False)
                if media_player_loaded:
                    await hass.config_entries.async_unload_platforms(
                        entry, [Platform.MEDIA_PLAYER]
                    )
                    media_player_loaded = False

    entry.async_on_unload(
        async_subscribe_preview_feature(
            hass,
            DOMAIN,
            "alexa_media",
            _async_update_alexa_media,
        )
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, non_labs_platforms)
    await _async_update_alexa_media()

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
