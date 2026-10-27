"""The TP-Link Omada integration."""

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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .config_flow import CONF_SITE, create_omada_client
from .const import DOMAIN
from .controller import OmadaSiteController
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

    # The first refresh sweeps stale registry entries before platforms create
    # entities, so replaced devices do not push new entities onto suffixed IDs.
    await controller.initialize_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a device from the registry and drop its cached state."""
    mac = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    controller = config_entry.runtime_data
    controller_status = controller.controller_status_coordinator.data
    if mac is None or (controller_status is not None and mac == controller_status.mac):
        return False
    await controller.async_forget_device(mac)
    return True


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
