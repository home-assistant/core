"""Helper base entities for integrations that consume infrared emitters/receivers."""

from abc import abstractmethod
from collections.abc import Callable
import logging
from typing import override

from infrared_protocols.commands import Command as InfraredCommand
import voluptuous as vol

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from .const import DATA_COMPONENT, DOMAIN
from .entity import (
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: InfraredCommand,
    context: Context | None = None,
) -> None:
    """Send an IR command to the specified infrared entity.

    Raises:
        HomeAssistantError: If the infrared entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, InfraredEmitterEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


@callback
def async_subscribe_receiver(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    signal_callback: Callable[[InfraredReceivedSignal], None],
) -> CALLBACK_TYPE:
    """Subscribe to IR signals from a specific receiver entity.

    Raises:
        HomeAssistantError: If the receiver entity is not found.
    """
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="component_not_loaded",
        )

    ent_reg = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    except vol.Invalid as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id_or_uuid},
        ) from err

    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, InfraredReceiverEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity.async_subscribe_received_signal(signal_callback)


class InfraredConsumerEntity(Entity):
    """Base class for entities that track the availability of an infrared entity."""

    @callback
    def _async_track_availability(self, infrared_entity_id: str) -> CALLBACK_TYPE:
        """Track the availability of an infrared entity.

        Sets initial availability and subscribes to state changes.
        Returns an unsubscribe callback.
        """

        @callback
        def state_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            ir_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if ir_available != self.available:
                _LOGGER.info(
                    "Infrared entity %s used by %s is %s",
                    infrared_entity_id,
                    self.entity_id,
                    "available" if ir_available else "unavailable",
                )
                self._async_infrared_availability_changed(ir_available)

        ir_state = self.hass.states.get(infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

        return async_track_state_change_event(
            self.hass, [infrared_entity_id], state_changed
        )

    @callback
    def _async_infrared_availability_changed(self, available: bool) -> None:
        """Update availability. Override to react to changes."""
        self._attr_available = available
        self.async_write_ha_state()


class InfraredEmitterConsumerEntity(InfraredConsumerEntity):
    """Base entity for integrations that send commands via an infrared emitter.

    Tracks the availability of the underlying infrared emitter entity.
    """

    _attr_should_poll = False
    _infrared_emitter_entity_id: str

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared entity state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._async_track_availability(self._infrared_emitter_entity_id)
        )

    async def _send_command(self, command: InfraredCommand) -> None:
        """Send an IR command through the infrared emitter entity."""
        await async_send_command(
            self.hass, self._infrared_emitter_entity_id, command, context=self._context
        )


class InfraredReceiverConsumerEntity(InfraredConsumerEntity):
    """Base entity for integrations that consume signals from an infrared receiver.

    Tracks the availability of the underlying infrared receiver entity and
    manages the subscription to received IR signals.
    """

    _attr_should_poll = False
    _infrared_receiver_entity_id: str
    _remove_signal_subscription: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared entity state changes and receiver signals."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._async_track_availability(self._infrared_receiver_entity_id)
        )

        self._async_update_receiver_subscription()
        self.async_on_remove(self._async_unsubscribe_receiver)

    @override
    @callback
    def _async_infrared_availability_changed(self, available: bool) -> None:
        """Update availability and manage receiver subscription."""
        super()._async_infrared_availability_changed(available)
        self._async_update_receiver_subscription()

    @callback
    @abstractmethod
    def _handle_signal(self, signal: InfraredReceivedSignal) -> None:
        """Handle a received IR signal."""

    @callback
    def _async_unsubscribe_receiver(self) -> None:
        """Unsubscribe from the current IR receiver."""
        if self._remove_signal_subscription is None:
            return
        self._remove_signal_subscription()
        self._remove_signal_subscription = None

    @callback
    def _async_update_receiver_subscription(self) -> None:
        """Update the IR receiver subscription when availability changes."""
        if not self.available:
            self._async_unsubscribe_receiver()
        elif self._remove_signal_subscription is None:
            _LOGGER.debug(
                "Subscribing to infrared receiver entity %s for %s",
                self._infrared_receiver_entity_id,
                self.entity_id,
            )
            self._remove_signal_subscription = async_subscribe_receiver(
                self.hass, self._infrared_receiver_entity_id, self._handle_signal
            )
