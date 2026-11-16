"""Fan for Shelly."""

from dataclasses import dataclass
from typing import Any, Final, override

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import get_device_entry_gen, get_rpc_channel_name

PARALLEL_UPDATES = 0

MODE_AUTO: Final = "auto"
MODE_MANUAL: Final = "manual"


@dataclass(frozen=True, kw_only=True)
class RpcFanDescription(RpcEntityDescription, FanEntityDescription):
    """Description for a Shelly RPC fan entity."""


RPC_FANS: Final = {
    "fan": RpcFanDescription(key="fan", translation_key="fan"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up fan entities."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return _async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return None


@callback
def _async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_FANS, RpcShellyFan
    )


class RpcShellyFan(ShellyRpcAttributeEntity, FanEntity):
    """Entity that controls a fan on RPC based Shelly devices."""

    entity_description: RpcFanDescription
    _id: int
    _attr_preset_modes = [MODE_AUTO, MODE_MANUAL]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcFanDescription,
    ) -> None:
        """Initialize fan."""
        super().__init__(coordinator, key, attribute, description)
        self._attr_name = get_rpc_channel_name(coordinator.device, key)
        self._attr_unique_id = f"{coordinator.mac}-{key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return bool(self.status["on"])

    @property
    @override
    def percentage(self) -> int:
        """Return the current speed percentage."""
        # The device keeps reporting the last speed while the fan is off
        return int(self.status["speed"]) if self.is_on else 0

    @property
    @override
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return str(self.status["mode"])

    @rpc_call
    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if preset_mode == MODE_AUTO:
            await self.async_set_preset_mode(preset_mode)
            return

        if percentage == 0:
            await self.async_turn_off()
            return

        await self.coordinator.device.fan_set(
            self._id, MODE_MANUAL, on=True, speed=percentage
        )

    @rpc_call
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.device.fan_set(self._id, MODE_MANUAL, on=False)

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.async_turn_on(percentage=percentage)

    @rpc_call
    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == MODE_AUTO:
            await self.coordinator.device.fan_set(self._id, MODE_AUTO)
            return

        # Keep the current output when leaving auto mode
        await self.coordinator.device.fan_set(
            self._id,
            MODE_MANUAL,
            on=self.is_on,
            speed=self.status["speed"] if self.is_on else None,
        )
