"""The TP-Link Omada integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from tplink_omada_client import OmadaSite
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .config_flow import CONF_SITE, create_omada_client
from .const import DOMAIN
from .controller import OmadaSiteController
from .coordinator import async_cleanup_client_trackers, async_cleanup_devices
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type OmadaConfigEntry = ConfigEntry[OmadaSiteController]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up TP-Link Omada integration."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Set up TP-Link Omada from a config entry."""

    try:
        client = await create_omada_client(hass, entry.data)
        await client.login()

    except (LoginFailed, UnsupportedControllerVersion) as ex:
        raise ConfigEntryAuthFailed(
            f"Omada controller refused login attempt: {ex}"
        ) from ex
    except ConnectionFailed as ex:
        raise ConfigEntryNotReady(
            f"Omada controller could not be reached: {ex}"
        ) from ex

    except OmadaClientException as ex:
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Omada controller: {ex}"
        ) from ex

    site_client = await client.get_site_client(OmadaSite("", entry.data[CONF_SITE]))
    controller = OmadaSiteController(hass, entry, site_client)

    entry.runtime_data = controller

    _cleanup_lock = asyncio.Lock()
    _first_cleanup_call = True

    async def _async_cleanup_task() -> None:
        nonlocal _first_cleanup_call
        async with _cleanup_lock:
            await async_cleanup_devices(
                hass,
                controller,
            )
            if not _first_cleanup_call:
                # Skip refresh on first run — data is already fresh from initialize_first_refresh()
                await controller.known_clients_coordinator.async_refresh()
            _first_cleanup_call = False
            await async_cleanup_client_trackers(
                hass,
                controller,
            )

    @callback
    def _schedule_cleanup(_now: datetime | None = None) -> None:
        if _cleanup_lock.locked():
            return
        entry.async_create_background_task(
            hass,
            _async_cleanup_task(),
            "tplink_omada cleanup",
        )

    await controller.initialize_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _schedule_cleanup()
    entry.async_on_unload(
        async_track_time_interval(hass, _schedule_cleanup, timedelta(hours=1))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
