"""Support for Switchbot switch."""
from logging import getLogger
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .common import CommonCommands, Device, PowerState, Remote
from .const import DOMAIN
from .entity import SwitchbotViaAPIEntity

_LOGGER = getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Awesome Light platform."""
    # Add devices
    add_entities(
        [
            SwitchBotViaAPISwitch(device)
            for device in hass.data[DOMAIN][Platform.SWITCH]
        ],
        update_before_add=True,
    )


class SwitchBotViaAPISwitch(SwitchbotViaAPIEntity, SwitchEntity):
    """Representation of a Switchbot switch."""

    _attr_is_on: bool | None = None

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, device: Device | Remote) -> None:
        """Initialize the entity."""
        super().__init__(device)
        if isinstance(device, Device) and device.device_type.startswith("Plug"):
            self._attr_device_class = SwitchDeviceClass.OUTLET

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.send_command(CommonCommands.ON)
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.send_command(CommonCommands.OFF)
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Update the entity."""
        await super().async_update()
        if self._switchbot_state is None:
            return
        self._attr_is_on = self._switchbot_state.get("power") == PowerState.ON.value
