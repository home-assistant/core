"""Switch platform for Gree IR integration — Gree AC features."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, override

from infrared_protocols.commands.gree_ac import GreeAcCommand

from homeassistant.components.infrared import (
    InfraredEmitterConsumerEntity,
    InfraredReceivedSignal,
    InfraredReceiverConsumerEntity,
)
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import GreeAcState, GreeIrConfigEntry
from .const import CONF_INFRARED_EMITTER_ENTITY_ID, CONF_INFRARED_RECEIVER_ENTITY_ID
from .entity import GreeIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class GreeAcSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Gree AC feature carried as one flag of every state frame."""

    value_fn: Callable[[GreeAcState], bool]
    set_value_fn: Callable[[GreeAcState, bool], GreeAcState]


SWITCH_DESCRIPTIONS: tuple[GreeAcSwitchEntityDescription, ...] = (
    GreeAcSwitchEntityDescription(
        key="turbo",
        translation_key="turbo",
        value_fn=lambda state: state.turbo,
        set_value_fn=lambda state, value: replace(state, turbo=value),
    ),
    GreeAcSwitchEntityDescription(
        key="light",
        translation_key="light",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.display,
        set_value_fn=lambda state, value: replace(state, display=value),
    ),
    GreeAcSwitchEntityDescription(
        key="xfan",
        translation_key="xfan",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.blow,
        set_value_fn=lambda state, value: replace(state, blow=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gree AC switches from a config entry."""
    emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    if receiver_entity_id := entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        async_add_entities(
            GreeAcSwitchWithReceiver(
                entry, emitter_entity_id, receiver_entity_id, description
            )
            for description in SWITCH_DESCRIPTIONS
        )
    else:
        async_add_entities(
            GreeAcSwitch(entry, emitter_entity_id, description)
            for description in SWITCH_DESCRIPTIONS
        )


class GreeAcSwitch(
    GreeIrEntity, InfraredEmitterConsumerEntity, SwitchEntity, RestoreEntity
):
    """A Gree AC feature carried by every state frame."""

    _attr_assumed_state = True
    entity_description: GreeAcSwitchEntityDescription

    def __init__(
        self,
        entry: GreeIrConfigEntry,
        emitter_entity_id: str,
        description: GreeAcSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, unique_id_suffix=description.key)
        self._infrared_emitter_entity_id = emitter_entity_id
        self.entity_description = description
        self._attr_is_on = description.value_fn(self._runtime_data.ac_state)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self._attr_is_on = last_state.state == STATE_ON

        self._record_state(bool(self._attr_is_on))

    def _record_state(self, is_on: bool) -> None:
        """Record this feature in the state shared with the other entities."""
        self._runtime_data.ac_state = self.entity_description.set_value_fn(
            self._runtime_data.ac_state, is_on
        )

    async def _async_send_state(self, is_on: bool) -> None:
        """Send a frame carrying this feature alongside the rest of the state."""
        async with self._runtime_data.send_lock:
            await self._send_command(
                self.entity_description.set_value_fn(
                    self._runtime_data.ac_state, is_on
                ).to_command()
            )
            self._record_state(is_on)
        self._attr_is_on = is_on
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the feature on."""
        await self._async_send_state(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the feature off."""
        await self._async_send_state(False)


class GreeAcSwitchWithReceiver(GreeAcSwitch, InfraredReceiverConsumerEntity):
    """A Gree AC feature switch that also tracks a configured infrared receiver."""

    def __init__(
        self,
        entry: GreeIrConfigEntry,
        emitter_entity_id: str,
        receiver_entity_id: str,
        description: GreeAcSwitchEntityDescription,
    ) -> None:
        """Initialize the switch with a receiver."""
        super().__init__(entry, emitter_entity_id, description)
        self._infrared_receiver_entity_id = receiver_entity_id

    @override
    @callback
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Update state from a physical remote signal."""
        command = GreeAcCommand.from_raw_timings(signal.timings)
        if command is None or not self._runtime_data.apply_received_command(command):
            return

        self._attr_is_on = self.entity_description.value_fn(self._runtime_data.ac_state)
        self.async_write_ha_state()
