"""Support for Tuya Smart devices."""

from typing import Any, NamedTuple

from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    LOGGER,
    TUYA_CLIENT_ID,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
)

type TuyaConfigEntry = ConfigEntry[HomeAssistantTuyaData]


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener


def create_manager(entry: TuyaConfigEntry, token_listener: TokenListener) -> Manager:
    """Create a Tuya Manager instance."""
    return Manager(
        TUYA_CLIENT_ID,
        entry.data[CONF_USER_CODE],
        entry.data[CONF_TERMINAL_ID],
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_TOKEN_INFO],
        token_listener,
    )


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
