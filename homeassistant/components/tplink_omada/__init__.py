"""The TP-Link Omada integration."""

import logging

from tplink_omada_client import OmadaSite
from tplink_omada_client.devices import OmadaListDevice
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
from homeassistant.helpers import config_validation as cv, device_registry as dr
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


async def async_setup_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
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
    controller = OmadaSiteController(hass, entry, site_client)
    await controller.initialize_first_refresh()

    entry.runtime_data = controller

    _remove_old_devices(hass, entry, controller.devices_coordinator.data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_old_devices(
    hass: HomeAssistant,
    entry: OmadaConfigEntry,
    omada_devices: dict[str, OmadaListDevice],
) -> None:
    device_registry = dr.async_get(hass)

    for registered_device in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        mac = next(
            (i[1] for i in registered_device.identifiers if i[0] == DOMAIN), None
        )
        if mac and mac not in omada_devices:
            device_registry.async_remove_device(registered_device.id)


async def async_migrate_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
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

    return True
