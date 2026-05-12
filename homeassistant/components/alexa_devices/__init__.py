"""Alexa Devices integration."""

import asyncio
import contextlib

from aioamazondevices.exceptions import CannotAuthenticate, CannotConnect
import httpx

from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_validation as cv, httpx_client
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .const import (
    _LOGGER,
    CONF_LOGIN_DATA,
    CONF_SITE,
    COUNTRY_DOMAINS,
    DOMAIN,
    HTTP2_RECONNECT_DELAY,
)
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


class Http2Manager:
    """Manages the HTTP2 task lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AmazonConfigEntry,
        coordinator: AmazonDevicesCoordinator,
        client: httpx.AsyncClient,
    ) -> None:
        """Initialize the HTTP2 manager."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._client = client
        self._task: asyncio.Task | None = None
        self._restart_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the HTTP2 task."""
        self._task = await self._coordinator.api.start_http2_processing(self._client)
        self._task.add_done_callback(self._on_task_done)

    async def cancel(self) -> None:
        """Cancel the HTTP2 task and any pending restart on unload."""
        if self._restart_task is not None and not self._restart_task.done():
            self._restart_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._restart_task

        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _restart(self) -> None:
        """Restart the HTTP2 task after a delay."""
        await asyncio.sleep(HTTP2_RECONNECT_DELAY)
        await self.start()

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Handle HTTP2 task completion."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return

        exceptions = exc.exceptions if isinstance(exc, ExceptionGroup) else [exc]

        start_reauth = False
        restart_http2 = False

        for e in exceptions:
            if isinstance(e, CannotAuthenticate):
                _LOGGER.error(
                    "HTTP2 auth failure", exc_info=(type(e), e, e.__traceback__)
                )
                start_reauth = True
            elif isinstance(e, CannotConnect):
                _LOGGER.warning(
                    "HTTP2 connection failure, restarting in %s seconds",
                    HTTP2_RECONNECT_DELAY,
                    exc_info=(type(e), e, e.__traceback__),
                )
                restart_http2 = True
            else:
                _LOGGER.error(
                    "Unexpected HTTP2 failure, restarting in %s seconds",
                    HTTP2_RECONNECT_DELAY,
                    exc_info=(type(e), e, e.__traceback__),
                )
                restart_http2 = True

        if start_reauth:
            self._entry.async_start_reauth(self._hass)
        elif restart_http2:
            self._restart_task = self._hass.async_create_task(self._restart())


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Alexa Devices component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Set up Alexa Devices platform."""

    session = aiohttp_client.async_create_clientsession(hass)
    coordinator = AmazonDevicesCoordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    await coordinator.sync_media_state()

    alexa_httpx_client = httpx_client.get_async_client(
        hass,
        alpn_protocols=SSL_ALPN_HTTP11_HTTP2,
    )
    http2_manager = Http2Manager(hass, entry, coordinator, alexa_httpx_client)
    await http2_manager.start()
    entry.async_on_unload(http2_manager.cancel)

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmazonConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        await entry.runtime_data.api.stop_http2_processing()
    except Exception:  # noqa: BLE001
        _LOGGER.error("Error while stopping http2 task", exc_info=True)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
