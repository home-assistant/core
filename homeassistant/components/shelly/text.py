"""Text for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.text import (
    DOMAIN as TEXT_PLATFORM,
    TextEntity,
    TextEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShellyConfigEntry
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_virtual_component_ids,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RpcTextDescription(RpcEntityDescription, TextEntityDescription):
    """Class to describe a RPC text entity."""


RPC_TEXT_ENTITIES: Final = {
    "text": RpcTextDescription(
        key="text",
        sub_key="value",
        has_entity_name=True,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        coordinator = config_entry.runtime_data.rpc
        assert coordinator

        async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_TEXT_ENTITIES, RpcText
        )

        # the user can remove virtual components from the device configuration, so
        # we need to remove orphaned entities
        virtual_text_ids = get_virtual_component_ids(
            coordinator.device.config, TEXT_PLATFORM
        )
        async_remove_orphaned_entities(
            hass,
            config_entry.entry_id,
            coordinator.mac,
            TEXT_PLATFORM,
            virtual_text_ids,
            "text",
        )


class RpcText(ShellyRpcAttributeEntity, TextEntity):
    """Represent a RPC text entity."""

    entity_description: RpcTextDescription
    attribute_value: str | None
    _id: int

    @property
    def native_value(self) -> str | None:
        """Return value of sensor."""
        return self.attribute_value

    @rpc_call
    async def async_set_value(self, value: str) -> None:
        """Change the value."""
        await self.coordinator.device.text_set(self._id, value)
