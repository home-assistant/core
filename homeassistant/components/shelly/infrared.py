"""Infrared platform for Shelly."""

from dataclasses import dataclass
from typing import Any, Final, override

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredEmitterEntityDescription,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
    InfraredReceiverEntityDescription,
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

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RpcInfraredEmitterEntityDescription(
    RpcEntityDescription, InfraredEmitterEntityDescription
):
    """Class to describe a Shelly RPC infrared emitter entity."""


@dataclass(frozen=True, kw_only=True)
class RpcInfraredReceiverEntityDescription(
    RpcEntityDescription, InfraredReceiverEntityDescription
):
    """Class to describe a Shelly RPC infrared receiver entity."""


class ShellyInfraredEmitter(ShellyRpcAttributeEntity, InfraredEmitterEntity):
    """Representation of a Shelly infrared emitter."""

    _attr_has_entity_name = True
    entity_description: RpcInfraredEmitterEntityDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcInfraredEmitterEntityDescription,
    ) -> None:
        """Initialize the infrared emitter."""
        super().__init__(coordinator, key, attribute, description)

    @rpc_call
    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via IR.EmitRaw."""
        await self.coordinator.device.ir_emit_raw(
            command.get_raw_timings(),
            command.modulation,
            command.repeat_count,
        )


class ShellyInfraredReceiver(ShellyRpcAttributeEntity, InfraredReceiverEntity):
    """Representation of a Shelly infrared receiver."""

    _attr_has_entity_name = True
    entity_description: RpcInfraredReceiverEntityDescription

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcInfraredReceiverEntityDescription,
    ) -> None:
        """Initialize the infrared receiver."""
        super().__init__(coordinator, key, attribute, description)

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to HASS."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_events(self._handle_device_event)
        )

    @callback
    def _handle_device_event(self, event: dict[str, Any]) -> None:
        """Handle a device event."""
        if event.get("component") != "ir" or event.get("event") != "raw_receive":
            return

        timings = event.get("timings")
        if not isinstance(timings, list) or not timings:
            return

        self._handle_received_signal(InfraredReceivedSignal(timings=timings))


RPC_INFRARED_ENTITIES: Final = {
    "infrared_emitter": RpcInfraredEmitterEntityDescription(
        key="ir",
        translation_key="infrared_emitter",
        entity_class=ShellyInfraredEmitter,
    ),
    "infrared_receiver": RpcInfraredReceiverEntityDescription(
        key="ir",
        translation_key="infrared_receiver",
        entity_class=ShellyInfraredReceiver,
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
