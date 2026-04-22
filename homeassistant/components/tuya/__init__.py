"""Support for Tuya Smart devices."""

from __future__ import annotations

import logging
from pathlib import Path

from tuya_device_handlers.devices import register_tuya_quirks
from tuya_sharing import Manager

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr
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
from .coordinator import DeviceListener, TokenListener, TuyaConfigEntry, create_manager
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tuya Services."""
    await async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Async setup hass config entry."""
    await hass.async_add_executor_job(
        register_tuya_quirks, str(Path(hass.config.config_dir, "tuya_quirks"))
    )

    token_listener = TokenListener(hass, entry)

    # Move to executor as it makes blocking call to import_module
    # with args ('.system', 'urllib3.contrib.resolver')
    manager = await hass.async_add_executor_job(create_manager, entry, token_listener)

    listener = DeviceListener(hass, manager)
    manager.add_device_listener(listener)

    # Get all devices from Tuya
    try:
        await hass.async_add_executor_job(manager.update_device_cache)
    except Exception as exc:
        # While in general, we should avoid catching broad exceptions,
        # we have no other way of detecting this case.
        if "sign invalid" in str(exc):
            msg = "Authentication failed. Please re-authenticate"
            raise ConfigEntryAuthFailed(msg) from exc
        raise

    # Connection is successful, store the listener in runtime_data
    entry.runtime_data = listener

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
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            manufacturer="Tuya",
            name=device.name,
            # Note: the model is overridden via entity.device_info property
            # when the entity is created. If no entities are generated, it will
            # stay as unsupported
            model=f"{device.product_name} (unsupported)",
            model_id=device.product_id,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # If the device does not register any entities, the device does not need to subscribe
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
                device_registry.async_update_device(
                    device_entry.id, remove_config_entry_id=entry.entry_id
                )
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
