"""Helper base entities for integrations that consume RF transmitters/receivers."""

from abc import abstractmethod
from collections.abc import Callable
import logging
from typing import override

import probatio
from rf_protocols import RadioFrequencyCommand

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
    RadioFrequencyReceivedSignal,
    RadioFrequencyReceiverEntity,
    RadioFrequencyTransmitterEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: RadioFrequencyCommand,
    context: Context | None = None,
) -> None:
    """Send an RF command to the specified radio_frequency entity.

    Raises:
        probatio.Invalid: If `entity_id_or_uuid` is not a valid entity ID or known entity
            registry UUID.
        HomeAssistantError: If the radio_frequency component is not loaded or the
            resolved entity is not found.
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
    if entity is None or not isinstance(entity, RadioFrequencyTransmitterEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if not entity.supports_frequency(command.frequency):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_frequency",
            translation_placeholders={
                "entity_id": entity_id,
                "frequency": str(command.frequency),
            },
        )

    if not entity.supports_modulation(command.modulation):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_modulation",
            translation_placeholders={
                "entity_id": entity_id,
                "modulation": command.modulation,
            },
        )

    if context is not None:
        entity.async_set_context(context)

    await entity.async_send_command_internal(command)


@callback
def async_subscribe_receiver(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    signal_callback: Callable[[RadioFrequencyReceivedSignal], None],
) -> CALLBACK_TYPE:
    """Subscribe to RF signals from a specific receiver entity.

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
    except probatio.Invalid as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id_or_uuid},
        ) from err

    entity = component.get_entity(entity_id)
    if entity is None or not isinstance(entity, RadioFrequencyReceiverEntity):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="receiver_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity.async_subscribe_received_signal(signal_callback)


# pylint: disable-next=home-assistant-enforce-class-module
class RadioFrequencyConsumerEntity(Entity):
    """Base class for entities that track the availability of RF entities.

    The entity is available only while all tracked RF entities are available.
    """

    _rf_availability: dict[str, bool]

    @override
    async def async_added_to_hass(self) -> None:
        """Initialize RF availability tracking."""
        await super().async_added_to_hass()
        self._rf_availability = {}

    @callback
    def _async_track_availability(self, rf_entity_id: str) -> CALLBACK_TYPE:
        """Track the availability of an RF entity.

        Sets initial availability and subscribes to state changes.
        Returns an unsubscribe callback.
        """

        @callback
        def state_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            rf_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if rf_available == self._rf_availability[rf_entity_id]:
                return
            _LOGGER.info(
                "Radio frequency entity %s used by %s is %s",
                rf_entity_id,
                self.entity_id,
                "available" if rf_available else "unavailable",
            )
            self._rf_availability[rf_entity_id] = rf_available
            available = all(self._rf_availability.values())
            if available != self.available:
                self._async_rf_availability_changed(available)

        @callback
        def unsubscribe() -> None:
            remove_listener()
            self._rf_availability.pop(rf_entity_id, None)

        rf_state = self.hass.states.get(rf_entity_id)
        self._rf_availability[rf_entity_id] = (
            rf_state is not None and rf_state.state != STATE_UNAVAILABLE
        )
        available = all(self._rf_availability.values())
        if available != self.available:
            self._async_rf_availability_changed(available)

        remove_listener = async_track_state_change_event(
            self.hass, [rf_entity_id], state_changed
        )
        return unsubscribe

    @callback
    def _async_rf_availability_changed(self, available: bool) -> None:
        """Update availability. Override to react to changes."""
        self._attr_available = available
        self.async_write_ha_state()


class RadioFrequencyTransmitterConsumerEntity(RadioFrequencyConsumerEntity):
    """Base entity for integrations that send commands via an RF transmitter.

    Tracks the availability of the underlying RF transmitter entity.
    """

    _attr_should_poll = False
    _rf_transmitter_entity_id: str

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to RF entity state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._async_track_availability(self._rf_transmitter_entity_id)
        )

    async def _send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command through the RF transmitter entity."""
        await async_send_command(
            self.hass,
            self._rf_transmitter_entity_id,
            command,
            context=self._context,
        )


class RadioFrequencyReceiverConsumerEntity(RadioFrequencyConsumerEntity):
    """Base entity for integrations that consume signals from an RF receiver.

    Tracks the availability of the underlying RF receiver entity and
    manages the subscription to received RF signals.
    """

    _attr_should_poll = False
    _rf_receiver_entity_id: str
    _remove_signal_subscription: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to RF entity state changes and receiver signals."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._async_track_availability(self._rf_receiver_entity_id)
        )

        self._async_update_receiver_subscription()
        self.async_on_remove(self._async_unsubscribe_receiver)

    @override
    @callback
    def _async_rf_availability_changed(self, available: bool) -> None:
        """Update availability and manage receiver subscription."""
        super()._async_rf_availability_changed(available)
        self._async_update_receiver_subscription()

    @callback
    @abstractmethod
    def _handle_signal(self, signal: RadioFrequencyReceivedSignal) -> None:
        """Handle a received RF signal."""

    @callback
    def _async_unsubscribe_receiver(self) -> None:
        """Unsubscribe from the current RF receiver."""
        if self._remove_signal_subscription is None:
            return
        self._remove_signal_subscription()
        self._remove_signal_subscription = None

    @callback
    def _async_update_receiver_subscription(self) -> None:
        """Update the RF receiver subscription when availability changes."""
        if not self.available:
            self._async_unsubscribe_receiver()
        elif self._remove_signal_subscription is None:
            _LOGGER.debug(
                "Subscribing to radio frequency receiver entity %s for %s",
                self._rf_receiver_entity_id,
                self.entity_id,
            )
            self._remove_signal_subscription = async_subscribe_receiver(
                self.hass, self._rf_receiver_entity_id, self._handle_signal
            )
