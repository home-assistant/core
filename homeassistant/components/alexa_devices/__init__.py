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

    session = aiohttp_client.async_create_clientsession(hass)
    coordinator = AmazonDevicesCoordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    media_player_loaded = False

    alexa_httpx_client = httpx_client.get_async_client(
        hass,
        alpn_protocols=SSL_ALPN_HTTP11_HTTP2,
    )
    http2_task: asyncio.Task | None = None

    async def _on_http2_reauth_required() -> None:
        entry.async_start_reauth(hass)

    async def _cancel_http2() -> None:
        nonlocal http2_task  # to be removed after labs
        if not http2_task:
            return
        http2_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await http2_task
        http2_task = None  # to be removed after labs

    async def _async_update_alexa_media(
        event_data: EventLabsUpdatedData | None = None,
    ) -> None:
        nonlocal media_player_loaded
        nonlocal http2_task

        enabled = (
            event_data["enabled"]
            if event_data is not None
            else async_is_preview_feature_enabled(hass, DOMAIN, "alexa_media")
        )

        if enabled:
            await coordinator.sync_media_state()
            http2_task = await coordinator.api.start_http2_processing(
                alexa_httpx_client,
                on_reauth_required=_on_http2_reauth_required,
            )

            if not media_player_loaded:
                await hass.config_entries.async_forward_entry_setups(
                    entry, [Platform.MEDIA_PLAYER]
                )
                media_player_loaded = True
        else:
            await _cancel_http2()
            if media_player_loaded:
                await hass.config_entries.async_unload_platforms(
                    entry, [Platform.MEDIA_PLAYER]
                )
                media_player_loaded = False

                # Remove entities from the registry so they don't show as unavailable
                ent_reg = er.async_get(hass)
                entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
                for entity in entities:
                    if entity.domain == Platform.MEDIA_PLAYER:
                        ent_reg.async_remove(entity.entity_id)

    entry.async_on_unload(
        async_subscribe_preview_feature(
            hass,
            DOMAIN,
            "alexa_media",
            _async_update_alexa_media,
        )
    )
    entry.async_on_unload(_cancel_http2)

    entry.runtime_data = coordinator

    NON_LABS_PLATFORMS = [p for p in PLATFORMS if p != Platform.MEDIA_PLAYER]
    await hass.config_entries.async_forward_entry_setups(entry, NON_LABS_PLATFORMS)

    await _async_update_alexa_media()

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        await entry.runtime_data.api.stop_http2_processing()
    except Exception:  # noqa: BLE001
        _LOGGER.error("Error while stopping http2 task", exc_info=True)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
