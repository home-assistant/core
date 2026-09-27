"""Fans controlled by Shelly 0-10 V dimmers."""

from typing import Any, override

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import ShellyRpcEntity
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_rpc_channel_name,
    get_rpc_key_id,
    get_rpc_key_instances,
    is_rpc_light_as_fan,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shelly fans."""
    if get_device_entry_gen(config_entry) not in RPC_GENERATIONS:
        return

    coordinator = config_entry.runtime_data.rpc
    assert coordinator
    keys = (
        get_rpc_key_instances(coordinator.device.status, "light")
        if is_rpc_light_as_fan(config_entry)
        else []
    )
    async_remove_orphaned_entities(
        hass, config_entry.entry_id, coordinator.mac, FAN_DOMAIN, keys
    )
    async_add_entities(ShellyFan(coordinator, key) for key in keys)


class ShellyFan(ShellyRpcEntity, FanEntity):
    """Represent a fan controlled by a 0-10 V output."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: ShellyRpcCoordinator, key: str) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, key)
        self._attr_name = get_rpc_channel_name(coordinator.device, key)
        self._id = get_rpc_key_id(key)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the output is on."""
        return bool(self.status["output"])

    @property
    @override
    def percentage(self) -> int:
        """Return output percentage, or zero when the fan is off."""
        return round(self.status["brightness"]) if self.is_on else 0

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan, optionally setting its speed."""
        if percentage == 0:
            await self.async_turn_off()
            return
        params: dict[str, Any] = {"id": self._id, "on": True}
        if percentage is not None:
            params["brightness"] = percentage
        await self.call_rpc("Light.Set", params)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.call_rpc("Light.Set", {"id": self._id, "on": False})

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed."""
        await self.async_turn_on(percentage=percentage)
