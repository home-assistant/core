"""The TP-Link Omada integration."""

from __future__ import annotations

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
from homeassistant.helpers.typing import ConfigType

from .cleanup import async_cleanup_client_trackers, async_cleanup_devices
from .config_flow import CONF_SITE, create_omada_client
from .const import DOMAIN
from .controller import OmadaSiteController
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

    async def _async_cleanup_task() -> None:
        await async_cleanup_devices(
            hass,
            config_entry_ids={entry.entry_id},
        )
        await async_cleanup_client_trackers(
            hass,
            config_entry_ids={entry.entry_id},
            raise_on_error=False,
        )

    @callback
    def _schedule_cleanup() -> None:
        entry.async_create_background_task(
            hass,
            _async_cleanup_task(),
            "tplink_omada cleanup",
        )

    entry.async_on_unload(
        controller.devices_coordinator.async_add_listener(_schedule_cleanup)
    )

    await controller.initialize_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
