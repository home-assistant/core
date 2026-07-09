"""The TP-Link Omada integration."""

import logging
from typing import cast

from tplink_omada_client import OmadaSite
from tplink_omada_client.devices import OmadaListDevice
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
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

_CONTROLLER_OWNER_STATES = {
    ConfigEntryState.LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up TP-Link Omada integration."""
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Set up TP-Link Omada from a config entry."""

    try:
        client = await create_omada_client(hass, entry.data)
        controller_id = await client.login()
        controller_name = await client.get_controller_name()

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
    controller = OmadaSiteController(
        hass, entry, client, site_client, controller_id, controller_name
    )
    await controller.initialize_first_refresh()

    entry.runtime_data = controller

    if config_entry_owns_controller_entities(hass, entry):
        _register_controller_device(hass, entry)

    _remove_old_devices(hass, entry, controller.devices_coordinator.data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OmadaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def config_entry_owns_controller_entities(
    hass: HomeAssistant,
    entry: OmadaConfigEntry,
) -> bool:
    """Return if this entry should own controller-level entities."""
    controller_id = entry.runtime_data.controller_id
    entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if _config_entry_matches_controller(config_entry, controller_id)
    ]
    active_entries = [
        config_entry
        for config_entry in entries
        if config_entry.state in _CONTROLLER_OWNER_STATES
    ]

    # Omada supports clustering internally, but the public Northbound API does
    # not document how to determine the current Primary controller.
    # Until a documented API is available, use a deterministic stable owner.
    candidate_entries = active_entries or entries
    owner = min(candidate_entries, key=lambda item: (item.created_at, item.entry_id))
    return owner.entry_id == entry.entry_id


def _config_entry_matches_controller(
    entry: ConfigEntry,
    controller_id: str,
) -> bool:
    if (runtime_data := getattr(entry, "runtime_data", None)) is not None:
        return cast(OmadaSiteController, runtime_data).controller_id == controller_id
    return entry.unique_id is not None and entry.unique_id.startswith(
        f"{controller_id}_"
    )


def _register_controller_device(
    hass: HomeAssistant,
    entry: OmadaConfigEntry,
) -> None:
    controller = entry.runtime_data
    controller_info = controller.controller_coordinator.data.info
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.controller_id)},
        manufacturer="TP-Link",
        model=controller.controller_name,
        name=controller.controller_name,
        sw_version=controller_info.controller_version,
    )


def _remove_old_devices(
    hass: HomeAssistant,
    entry: OmadaConfigEntry,
    omada_devices: dict[str, OmadaListDevice],
) -> None:
    device_registry = dr.async_get(hass)
    controller_id = entry.runtime_data.controller_id

    for registered_device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        mac = next(
            (i[1] for i in registered_device.identifiers if i[0] == DOMAIN), None
        )
        if mac and mac != controller_id and mac not in omada_devices:
            device_registry.async_update_device(
                registered_device.id, remove_config_entry_id=entry.entry_id
            )


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
