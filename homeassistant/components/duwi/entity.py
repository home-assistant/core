"""Base class for DUWI device types integration."""

from typing import Any

from duwi_smarthome_sdk.device_scene_models import CustomerDevice
from duwi_smarthome_sdk.manager import Manager

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, DUWI_HA_SIGNAL_UPDATE_ENTITY, MANUFACTURER


class DuwiEntity(Entity):
    """Duwi base device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Initialize the Duwi entity."""
        self._attr_unique_id = f"duwi.{device.device_no}"
        self.device = device
        self.entity_id = f"{DOMAIN}.{device.device_no}"
        self.device_manager = device_manager

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for the device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_no)},
            manufacturer=MANUFACTURER,
            name=f"{self.device.room_name + ' ' if self.device.room_name else 'default room'} {self.device.device_name}",
            model=self.device.device_type,
            suggested_area=f"{self.device.floor_name} {self.device.room_name}".strip(),
        )

    async def async_added_to_hass(self) -> None:
        """Handle the addition of the entity to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DUWI_HA_SIGNAL_UPDATE_ENTITY}_{self.device.device_no}",
                self.handle_signal,
            )
        )

    async def handle_signal(self) -> None:
        """Handle the signal and invoke the appropriate method based on is_control."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device.value.get("online", False)

    async def _send_command(self, commands: dict[str, Any]) -> None:
        """Send command to the device."""
        self.device.value.update(commands)
        await self.device_manager.send_commands(
            self.device.device_no, self.device.is_group, commands
        )
