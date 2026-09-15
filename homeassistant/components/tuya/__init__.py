"""Support for Tuya Smart devices."""

import logging

from tuya_sharing import Manager

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    TUYA_CLIENT_ID,
)
from .coordinator import DeviceListener, TuyaConfigEntry
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tuya Services."""
    async_setup_services(hass)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version > 1:
        # Downgraded from a future version, we can't handle that
        return False

    if entry.version == 1 and entry.minor_version < 2:
        await _async_migrate_entity_unique_ids(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def _async_migrate_entity_unique_ids(
    hass: HomeAssistant, entry: TuyaConfigEntry
) -> None:
    """Drop the redundant `tuya.` prefix from entity unique IDs.

    Old format: `tuya.{device_id}{key}`, new format: `{device_id}.{key}`.
    Added in 2026.10.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    @callback
    def _migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, str] | None:
        """Return the updated unique ID, if the entity needs migrating."""
        if entity_entry.device_id is None or not (
            device_entry := device_registry.async_get(entity_entry.device_id)
        ):
            return None
        device_id = next(
            (
                identifier[1]
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            ),
            None,
        )
        if device_id is None:
            return None

        old_prefix = f"{DOMAIN}.{device_id}"
        if not entity_entry.unique_id.startswith(old_prefix):
            return None

        new_unique_id = device_id
        if key := entity_entry.unique_id.removeprefix(old_prefix):
            new_unique_id = f"{device_id}.{key}"

        # A downgrade can leave a stale entity holding the new unique ID
        if entity_registry.async_get_entity_id(
            entity_entry.domain, DOMAIN, new_unique_id
        ):
            LOGGER.debug(
                "Not migrating %s, unique ID %s is already in use",
                entity_entry.entity_id,
                new_unique_id,
            )
            return None

        return {"new_unique_id": new_unique_id}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Async setup hass config entry."""
    listener = DeviceListener(hass, entry)
    await hass.async_add_executor_job(listener.initialize)

    # Connection is successful, store the listener in runtime_data
    entry.runtime_data = listener
    manager = listener.manager

    # Cleanup device registry
    await cleanup_device_registry(hass, manager, entry)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in manager.device_map.values():
        LOGGER.debug(
            "Register device %s (online: %s): %s (function: %s, status range: %s)",
            device.id,
            device.online,
            device.status,
            device.function,
            device.status_range,
        )
        # Register quirk, and add device to the device registry
        listener.async_register_device(device_registry, device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # If the device does not register any entities,
    # the device does not need to subscribe
    # So the subscription is here
    await hass.async_add_executor_job(manager.refresh_mq)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: Manager, entry: TuyaConfigEntry
) -> None:
    """Unlink device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(device_entry.id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        listener = entry.runtime_data
        manager = listener.manager
        if manager.mq is not None:
            manager.mq.stop()
        manager.remove_device_listener(listener)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    manager = Manager(
        TUYA_CLIENT_ID,
        entry.data[CONF_USER_CODE],
        entry.data[CONF_TERMINAL_ID],
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_TOKEN_INFO],
    )
    await hass.async_add_executor_job(manager.unload)
