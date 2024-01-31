"""Cover for Shelly."""
from __future__ import annotations

from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ShellyBlockCoordinator, ShellyRpcCoordinator, get_entry_data
from .entity import ShellyBlockEntity, ShellyRpcEntity
from .utils import get_device_entry_gen, get_rpc_key_ids


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up covers for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover for device."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].block
    assert coordinator and coordinator.device.blocks
    blocks = [block for block in coordinator.device.blocks if block.type == "roller"]

    if not blocks:
        return

    async_add_entities(BlockShellyCover(coordinator, block) for block in blocks)


@callback
def async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = get_entry_data(hass)[config_entry.entry_id].rpc
    assert coordinator
    cover_key_ids = get_rpc_key_ids(coordinator.device.status, "cover")

    if not cover_key_ids:
        return

    async_add_entities(RpcShellyCover(coordinator, id_) for id_ in cover_key_ids)


class BlockShellyCover(ShellyBlockEntity, CoverEntity):
    """Entity that controls a cover on block based Shelly devices."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator: ShellyBlockCoordinator, block: Block) -> None:
        """Initialize block cover."""
        super().__init__(coordinator, block)
        self.control_result: dict[str, Any] | None = None
        if self.coordinator.device.settings["rollers"][0]["positioning"]:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    @property
    def is_closed(self) -> bool:
        """If cover is closed."""
        if self.control_result:
            return cast(bool, self.control_result["current_pos"] == 0)

        return cast(int, self.block.rollerPos) == 0

    @property
    def current_cover_position(self) -> int:
        """Position of the cover."""
        if self.control_result:
            return cast(int, self.control_result["current_pos"])

        return cast(int, self.block.rollerPos)

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "close")

        return self.block.roller == "close"

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        if self.control_result:
            return cast(bool, self.control_result["state"] == "open")

        return self.block.roller == "open"

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self.control_result = await self.set_state(go="close")
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        self.control_result = await self.set_state(go="open")
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self.control_result = await self.set_state(
            go="to_pos", roller_pos=kwargs[ATTR_POSITION]
        )
        self.async_write_ha_state()

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        self.control_result = await self.set_state(go="stop")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()


class RpcShellyCover(ShellyRpcEntity, CoverEntity):
    """Entity that controls a cover on RPC based Shelly devices."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator: ShellyRpcCoordinator, id_: int) -> None:
        """Initialize rpc cover."""
        super().__init__(coordinator, f"cover:{id_}")
        self._id = id_
        if self.status["pos_control"]:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    @property
    def is_closed(self) -> bool | None:
        """If cover is closed."""
        return cast(bool, self.status["state"] == "closed")

    @property
    def current_cover_position(self) -> int | None:
        """Position of the cover."""
        if not self.status["pos_control"]:
            return None

        return cast(int, self.status["current_pos"])

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return cast(bool, self.status["state"] == "closing")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return cast(bool, self.status["state"] == "opening")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.call_rpc("Cover.Close", {"id": self._id})

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.call_rpc("Cover.Open", {"id": self._id})

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.call_rpc(
            "Cover.GoToPosition", {"id": self._id, "pos": kwargs[ATTR_POSITION]}
        )

    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        await self.call_rpc("Cover.Stop", {"id": self._id})
