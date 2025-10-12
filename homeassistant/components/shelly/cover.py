"""Cover for Shelly."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from aioshelly.block_device import Block
from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import RPC_COVER_UPDATE_TIME_SEC
from .coordinator import ShellyBlockCoordinator, ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    BlockEntityDescription,
    RpcEntityDescription,
    ShellyBlockAttributeEntity,
    ShellyRpcAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import get_device_entry_gen

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BlockCoverDescription(BlockEntityDescription, CoverEntityDescription):
    """Class to describe a BLOCK cover."""


@dataclass(frozen=True, kw_only=True)
class RpcCoverDescription(RpcEntityDescription, CoverEntityDescription):
    """Class to describe a RPC cover."""


BLOCK_COVERS = {
    ("roller", "roller"): BlockCoverDescription(
        key="roller|roller",
    )
}

RPC_COVERS = {
    "cover": RpcCoverDescription(
        key="cover",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover entities."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return _async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return _async_setup_block_entry(hass, config_entry, async_add_entities)


@callback
def _async_setup_block_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for BLOCK device."""
    coordinator = config_entry.runtime_data.block
    assert coordinator

    async_setup_entry_attribute_entities(
        hass, config_entry, async_add_entities, BLOCK_COVERS, BlockShellyCover
    )


@callback
def _async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator

    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_COVERS, RpcShellyCover
    )


class BlockShellyCover(ShellyBlockAttributeEntity, CoverEntity):
    """Entity that controls a cover on block based Shelly devices."""

    entity_description: BlockCoverDescription
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(
        self,
        coordinator: ShellyBlockCoordinator,
        block: Block,
        attribute: str,
        description: BlockCoverDescription,
    ) -> None:
        """Initialize block cover."""
        super().__init__(coordinator, block, attribute, description)
        self.control_result: dict[str, Any] | None = None
        self._attr_unique_id: str = f"{coordinator.mac}-{block.description}"
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


class RpcShellyCover(ShellyRpcAttributeEntity, CoverEntity):
    """Entity that controls a cover on RPC based Shelly devices."""

    entity_description: RpcCoverDescription
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _id: int

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcCoverDescription,
    ) -> None:
        """Initialize rpc cover."""
        super().__init__(coordinator, key, attribute, description)
        self._attr_unique_id: str = f"{coordinator.mac}-{key}"
        self._update_task: asyncio.Task | None = None
        self._update_status: dict[str, Any] | None = None
        if self.status["pos_control"]:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        if coordinator.device.config[key].get("slat", {}).get("enable"):
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

    @property
    def is_closed(self) -> bool | None:
        """If cover is closed."""
        return cast(bool, self.status["state"] == "closed")

    @property
    def current_cover_position(self) -> int | None:
        """Position of the cover."""
        if not self.status["pos_control"]:
            return None

        if self._update_status is not None:
            return cast(int, self._update_status["current_pos"])

        return cast(int, self.status["current_pos"])

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt."""
        if "slat_pos" not in self.status:
            return None

        return cast(int, self.status["slat_pos"])

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return cast(bool, self.status["state"] == "closing")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return cast(bool, self.status["state"] == "opening")

    def launch_update_task(self) -> None:
        """Launch the update position task if needed."""
        if not self._update_task or self._update_task.done():
            self._update_task = (
                self.coordinator.config_entry.async_create_background_task(
                    self.hass,
                    self.update_position(),
                    f"Shelly cover update [{self._id} - {self.name}]",
                )
            )

    async def update_position(self) -> None:
        """Update the cover position every second."""
        try:
            while self.is_closing or self.is_opening:
                self._update_status = await self.coordinator.device.cover_get_status(
                    self._id
                )
                self.async_write_ha_state()
                await asyncio.sleep(RPC_COVER_UPDATE_TIME_SEC)
        finally:
            self._update_task = None
            self._update_status = None

    def _update_callback(self) -> None:
        """Handle device update. Use a task when opening/closing is in progress."""
        super()._update_callback()
        if not self.coordinator.device.initialized:
            return
        if self.is_closing or self.is_opening:
            self.launch_update_task()

    @rpc_call
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.coordinator.device.cover_close(self._id)

    @rpc_call
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.coordinator.device.cover_open(self._id)

    @rpc_call
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.coordinator.device.cover_set_position(
            self._id, pos=kwargs[ATTR_POSITION]
        )

    @rpc_call
    async def async_stop_cover(self, **_kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.device.cover_stop(self._id)

    @rpc_call
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self.coordinator.device.cover_set_position(self._id, slat_pos=100)

    @rpc_call
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self.coordinator.device.cover_set_position(self._id, slat_pos=0)

    @rpc_call
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self.coordinator.device.cover_set_position(
            self._id, slat_pos=kwargs[ATTR_TILT_POSITION]
        )

    @rpc_call
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.device.cover_stop(self._id)
