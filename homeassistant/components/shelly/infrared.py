"""Infrared platform for Shelly."""

from dataclasses import dataclass
from typing import Final, override

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredEmitterEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RpcInfraredEntityDescription(
    RpcEntityDescription, InfraredEmitterEntityDescription
):
    """Class to describe a Shelly RPC infrared entity."""


RPC_INFRARED_ENTITIES: Final = {
    "infrared_emitter": RpcInfraredEntityDescription(
        key="ir",
        translation_key="infrared_emitter",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shelly infrared entities."""
    if not config_entry.runtime_data.rpc:
        return

    async_setup_entry_rpc(
        hass,
        config_entry,
        async_add_entities,
        RPC_INFRARED_ENTITIES,
        ShellyInfraredEmitter,
    )


class ShellyInfraredEmitter(ShellyRpcAttributeEntity, InfraredEmitterEntity):
    """Representation of a Shelly infrared emitter."""

    _attr_has_entity_name = True
    entity_description: RpcInfraredEntityDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcInfraredEntityDescription,
    ) -> None:
        """Initialize the infrared emitter."""
        super().__init__(coordinator, key, attribute, description)

    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via IR.EmitRaw."""
        timings = command.get_raw_timings()
        freq = command.modulation or 38000
        repeats = command.repeat_count or 0

        await self.call_rpc(
            "IR.EmitRaw",
            {"timings": timings, "freq": freq, "repeats": repeats},
        )
