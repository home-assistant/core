"""Support for ZHA infrared emitters and receivers."""

import functools
from typing import override

from zha.application.platforms.infrared import (
    BaseInfraredEmitter,
    BaseInfraredReceiver,
    EntityInfraredSignalReceivedEvent,
    InfraredSignal,
)

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation infrared from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.INFRARED]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities,
            async_add_entities,
            _make_infrared_entity,
            entities_to_create,
        ),
    )
    config_entry.async_on_unload(unsub)


def _make_infrared_entity(entity_data: EntityData) -> ZHAEntity:
    """Create the HA entity matching the ZHA infrared entity type."""
    if isinstance(entity_data.entity, BaseInfraredEmitter):
        return ZHAInfraredEmitter(entity_data)

    if isinstance(entity_data.entity, BaseInfraredReceiver):
        return ZHAInfraredReceiver(entity_data)

    raise TypeError(f"Unknown infrared entity: {entity_data.entity!r}")


class ZHAInfraredEmitter(ZHAEntity, InfraredEmitterEntity):
    """Representation of a ZHA infrared emitter."""

    @convert_zha_error_to_ha_error()
    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command."""
        await self.entity_data.entity.async_send_command(
            InfraredSignal(
                timings=command.get_raw_timings(),
                modulation=command.modulation,
            )
        )


class ZHAInfraredReceiver(ZHAEntity, InfraredReceiverEntity):
    """Representation of a ZHA infrared receiver."""

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to signals captured by the ZHA entity."""
        await super().async_added_to_hass()
        self._unsubs.append(
            self.entity_data.entity.on_event(
                EntityInfraredSignalReceivedEvent.event,
                self._handle_zha_received_signal,
            )
        )

    @callback
    def _handle_zha_received_signal(
        self, event: EntityInfraredSignalReceivedEvent
    ) -> None:
        """Handle a signal captured by the ZHA entity."""
        self._handle_received_signal(
            InfraredReceivedSignal(
                timings=event.signal.timings,
                modulation=event.signal.modulation,
            )
        )
