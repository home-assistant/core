"""Support for SwitchBot switch."""
from logging import getLogger
from typing import Any

from switchbot_api import CommonCommands, Device, PowerState, Remote, SwitchBotAPI

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import Data
from .const import DOMAIN
from .entity import SwitchBotCloudEntity

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: Data = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
         SwitchBotCloudSwitch(data.api, device, coordinator)
         for device, coordinator in data.switches
    )


class SwitchBotCloudSwitch(SwitchBotCloudEntity, SwitchEntity):
    """Representation of a SwitchBot switch."""

    _attr_is_on: bool | None = None
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(api, device, coordinator)
        if isinstance(device, Device) and device.device_type.startswith("Plug"):
            self._attr_device_class = SwitchDeviceClass.OUTLET

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.send_command(CommonCommands.ON)
        if self._is_remote:
            self._attr_is_on = True
        else:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_command(CommonCommands.OFF)
        if self._is_remote:
            self._attr_is_on = False
        else:
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        state = self.coordinator.data
        if state is None:
            return
        self._attr_is_on = state.get("power") == PowerState.ON.value
        self.async_write_ha_state()
