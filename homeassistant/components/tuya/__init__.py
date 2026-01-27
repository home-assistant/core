"""Support for Tuya Smart devices."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_DP_CODE,
    CONF_DP_VALUE,
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SERVICE_SET_DP_VALUE,
    TUYA_CLIENT_ID,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)

type TuyaConfigEntry = ConfigEntry[HomeAssistantTuyaData]


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener


def _create_manager(entry: TuyaConfigEntry, token_listener: TokenListener) -> Manager:
    """Create a Tuya Manager instance."""
    return Manager(
        TUYA_CLIENT_ID,
        entry.data[CONF_USER_CODE],
        entry.data[CONF_TERMINAL_ID],
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_TOKEN_INFO],
        token_listener,
    )


async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Async setup hass config entry."""
    token_listener = TokenListener(hass, entry)

    # Move to executor as it makes blocking call to import_module
    # with args ('.system', 'urllib3.contrib.resolver')
    manager = await hass.async_add_executor_job(_create_manager, entry, token_listener)

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

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantTuyaData(manager=manager, listener=listener)

    # Cleanup device registry
    await cleanup_device_registry(hass, manager)

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

    # Register services if not already registered
    _async_setup_services(hass)

    return True


# Service schema for set_dp_value
SERVICE_SET_DP_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DP_CODE): cv.string,
        vol.Required(CONF_DP_VALUE): vol.Any(
            bool,
            vol.Coerce(int),
            vol.Coerce(float),
            cv.string,
        ),
    }
)


@callback
def _get_tuya_device_id(
    hass: HomeAssistant, device_id: str
) -> tuple[Manager, str] | None:
    """Get Tuya device ID from HA device ID or Tuya device ID.

    Returns tuple of (manager, tuya_device_id) if found, None otherwise.
    """
    device_registry = dr.async_get(hass)

    # First, check if device_id is a HA device registry ID
    if device_entry := device_registry.async_get(device_id):
        # Extract Tuya device ID from identifiers
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                tuya_device_id = identifier[1]
                # Find the manager for this device
                for entry in hass.config_entries.async_entries(DOMAIN):
                    if entry.state is not ConfigEntryState.LOADED:
                        continue
                    manager: Manager = entry.runtime_data.manager
                    if tuya_device_id in manager.device_map:
                        return (manager, tuya_device_id)

    # If not found, assume device_id is a Tuya device ID
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        manager = entry.runtime_data.manager
        if device_id in manager.device_map:
            return (manager, device_id)

    return None


@callback
def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up Tuya services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_DP_VALUE):
        return

    async def async_set_dp_value(call: ServiceCall) -> None:
        """Set a DP value on a Tuya device."""
        device_id = call.data[CONF_DEVICE_ID]
        dp_code = call.data[CONF_DP_CODE]
        dp_value = call.data[CONF_DP_VALUE]

        # Find the device (supports both HA device ID and Tuya device ID)
        result = _get_tuya_device_id(hass, device_id)
        if result is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"device_id": device_id},
            )

        manager, tuya_device_id = result
        device = manager.device_map[tuya_device_id]

        # Check if device is online
        if not device.online:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_offline",
                translation_placeholders={"device_name": device.name},
            )

        # Validate DP code exists in device functions
        if not device.function or dp_code not in device.function:
            available_codes = list(device.function.keys()) if device.function else []
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_dp_code",
                translation_placeholders={
                    "dp_code": dp_code,
                    "device_name": device.name,
                    "available_codes": ", ".join(available_codes[:10])
                    + ("..." if len(available_codes) > 10 else "")
                    if available_codes
                    else "none",
                },
            )

        LOGGER.debug(
            "Sending DP command to device %s (%s): %s=%s",
            device.name,
            tuya_device_id,
            dp_code,
            dp_value,
        )

        try:
            await hass.async_add_executor_job(
                manager.send_commands,
                tuya_device_id,
                [{"code": dp_code, "value": dp_value}],
            )
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={
                    "device_name": device.name,
                    "error": str(err),
                },
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DP_VALUE,
        async_set_dp_value,
        schema=SERVICE_SET_DP_VALUE_SCHEMA,
    )


async def cleanup_device_registry(hass: HomeAssistant, device_manager: Manager) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager.mq is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listener(tuya.listener)

    # Unregister services if this is the last loaded entry
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_DP_VALUE)

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


class DeviceListener(SharingDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: Manager,
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.manager = manager

    def update_device(
        self,
        device: CustomerDevice,
        updated_status_properties: list[str] | None = None,
        dp_timestamps: dict[str, int] | None = None,
    ) -> None:
        """Update device status with optional DP timestamps."""
        LOGGER.debug(
            "Received update for device %s (online: %s): %s"
            " (updated properties: %s, dp_timestamps: %s)",
            device.id,
            device.online,
            device.status,
            updated_status_properties,
            dp_timestamps,
        )
        dispatcher_send(
            self.hass,
            f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}",
            updated_status_properties,
            dp_timestamps,
        )

    def add_device(self, device: CustomerDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        LOGGER.debug(
            "Add device %s (online: %s): %s (function: %s, status range: %s)",
            device.id,
            device.online,
            device.status,
            device.function,
            device.status_range,
        )

        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        LOGGER.debug("Remove device: %s", device_id)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)


class TokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TuyaConfigEntry,
    ) -> None:
        """Init TokenListener."""
        self.hass = hass
        self.entry = entry

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Update token info in config entry."""
        data = {
            **self.entry.data,
            CONF_TOKEN_INFO: {
                "t": token_info["t"],
                "uid": token_info["uid"],
                "expire_time": token_info["expire_time"],
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
            },
        }

        @callback
        def async_update_entry() -> None:
            """Update config entry."""
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        self.hass.add_job(async_update_entry)
