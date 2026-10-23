"""The TP-Link Omada integration."""

import asyncio
from datetime import datetime, timedelta
import logging

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
from .coordinator import async_cleanup_devices
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> None:
    """Set up TP-Link Omada from a config entry."""

    try:
        client = await create_omada_client(hass, entry.data)
        await client.login()

    except LoginFailed as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from ex
    except UnsupportedControllerVersion as ex:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="unsupported_controller",
        ) from ex
    except ConnectionFailed as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from ex

    except OmadaClientException as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unexpected_error",
        ) from ex

    site_client = await client.get_site_client(OmadaSite("", entry.data[CONF_SITE]))
    controller = OmadaSiteController(hass, entry, client, site_client)

    entry.runtime_data = controller

    _cleanup_task: asyncio.Task[None] | None = None

    async def _async_cleanup_task() -> None:
        if entry.pref_disable_polling:
            # Cleanup decisions need fresh data, so skip the run entirely
            # instead of polling the controller while polling is disabled.
            return
        # Refresh the coordinator so cleanup doesn't use stale data.
        await controller.devices_coordinator.async_refresh()
        await async_cleanup_devices(hass, controller)

    @callback
    def _schedule_cleanup(_now: datetime | None = None) -> None:
        nonlocal _cleanup_task
        if _cleanup_task is not None and not _cleanup_task.done():
            return
        _cleanup_task = entry.async_create_background_task(
            hass,
            _async_cleanup_task(),
            "tplink_omada cleanup",
        )

    await controller.initialize_first_refresh()

    # Sweep before platforms create entities, so a device that was replaced
    # while Home Assistant was stopped does not push the new entities onto
    # suffixed entity IDs that the stale entries still occupy.
    await async_cleanup_devices(hass, controller)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _cancel_cleanup() -> None:
        if _cleanup_task is not None and not _cleanup_task.done():
            _cleanup_task.cancel()

    entry.async_on_unload(_cancel_cleanup)
    entry.async_on_unload(
        async_track_time_interval(hass, _schedule_cleanup, timedelta(hours=1))
    )


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> None:
    """Migrate old config entry to a new format."""

    if entry.version == 1:
        # Migrate unique_id from controller_id to controller_id_site_id
        # to allow multiple sites per controller to be set up independently.
        _LOGGER.debug(
            "Migrating tplink_omada config entry from version %s.%s",
            entry.version,
            entry.minor_version,
        )

        hass.config_entries.async_update_entry(
            entry,
            unique_id=f"{entry.unique_id}_{entry.data[CONF_SITE]}",
            version=2,
        )
