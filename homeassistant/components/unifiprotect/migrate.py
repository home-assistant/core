"""UniFi Protect data migrations."""
from __future__ import annotations

import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from pyunifiprotect import ProtectApiClient
from pyunifiprotect.data import NVR, Bootstrap, ProtectAdoptableDeviceModel
from pyunifiprotect.exceptions import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


async def async_migrate_data(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """Run all valid UniFi Protect data migrations."""

    _LOGGER.debug("Start Migrate: async_migrate_buttons")
    await async_migrate_buttons(hass, entry, protect)
    _LOGGER.debug("Completed Migrate: async_migrate_buttons")

    _LOGGER.debug("Start Migrate: async_migrate_device_ids")
    await async_migrate_device_ids(hass, entry, protect)
    _LOGGER.debug("Completed Migrate: async_migrate_device_ids")


async def async_get_bootstrap(protect: ProtectApiClient) -> Bootstrap:
    """Get UniFi Protect bootstrap or raise appropriate HA error."""

    try:
        bootstrap = await protect.get_bootstrap()
    except (TimeoutError, ClientError, ServerDisconnectedError) as err:
        raise ConfigEntryNotReady from err

    return bootstrap


async def async_migrate_buttons(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """Migrate existing Reboot button unique IDs from {device_id} to {deivce_id}_reboot.

    This allows for additional types of buttons that are outside of just a reboot button.

    Added in 2022.6.0.
    """

    registry = er.async_get(hass)
    to_migrate = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == Platform.BUTTON and "_" not in entity.unique_id:
            _LOGGER.debug("Button %s needs migration", entity.entity_id)
            to_migrate.append(entity)

    if len(to_migrate) == 0:
        _LOGGER.debug("No button entities need migration")
        return

    bootstrap = await async_get_bootstrap(protect)
    count = 0
    for button in to_migrate:
        device = bootstrap.get_device_from_id(button.unique_id)
        if device is None:
            continue

        new_unique_id = f"{device.id}_reboot"
        _LOGGER.debug(
            "Migrating entity %s (old unique_id: %s, new unique_id: %s)",
            button.entity_id,
            button.unique_id,
            new_unique_id,
        )
        try:
            registry.async_update_entity(button.entity_id, new_unique_id=new_unique_id)
        except ValueError:
            _LOGGER.warning(
                "Could not migrate entity %s (old unique_id: %s, new unique_id: %s)",
                button.entity_id,
                button.unique_id,
                new_unique_id,
            )
        else:
            count += 1

    if count < len(to_migrate):
        _LOGGER.warning("Failed to migate %s reboot buttons", len(to_migrate) - count)


async def async_migrate_device_ids(
    hass: HomeAssistant, entry: ConfigEntry, protect: ProtectApiClient
) -> None:
    """Migrate unique IDs from {device_id}_{name} format to {mac}_{name} format.

    This makes devices persist better with in HA. Anything a device is unadopted/readopted or
    the Protect instance has to rebuild the disk array, the device IDs of Protect devices
    can change. This causes a ton of orphaned entities and loss of historical data. MAC
    addresses are the one persistent identifier a device has that does not change.

    Added in 2022.7.0.
    """

    registry = er.async_get(hass)
    to_migrate = []
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        parts = entity.unique_id.split("_")
        # device ID = 24 characters, MAC = 12
        if len(parts[0]) == 24:
            _LOGGER.debug("Entity %s needs migration", entity.entity_id)
            to_migrate.append(entity)

    if len(to_migrate) == 0:
        _LOGGER.debug("No entities need migration to MAC address ID")
        return

    bootstrap = await async_get_bootstrap(protect)
    count = 0
    for entity in to_migrate:
        parts = entity.unique_id.split("_")
        if parts[0] == bootstrap.nvr.id:
            device: NVR | ProtectAdoptableDeviceModel | None = bootstrap.nvr
        else:
            device = bootstrap.get_device_from_id(parts[0])

        if device is None:
            continue

        new_unique_id = device.mac
        if len(parts) > 1:
            new_unique_id = f"{device.mac}_{'_'.join(parts[1:])}"
        _LOGGER.debug(
            "Migrating entity %s (old unique_id: %s, new unique_id: %s)",
            entity.entity_id,
            entity.unique_id,
            new_unique_id,
        )
        try:
            registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
        except ValueError as err:
            _LOGGER.warning(
                (
                    "Could not migrate entity %s (old unique_id: %s, new unique_id:"
                    " %s): %s"
                ),
                entity.entity_id,
                entity.unique_id,
                new_unique_id,
                err,
            )
        else:
            count += 1

    if count < len(to_migrate):
        _LOGGER.warning("Failed to migrate %s entities", len(to_migrate) - count)
