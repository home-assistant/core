"""Helper base entities for integrations that consume RF transmitters."""

import logging
from typing import override

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
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)

from .const import DATA_COMPONENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_send_command(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
    command: RadioFrequencyCommand,
    context: Context | None = None,
) -> None:
    """Send an RF command to the specified radio_frequency entity.

    Raises:
        vol.Invalid: If `entity_id_or_uuid` is not a valid entity ID or known entity
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
    if entity is None:
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


class RadioFrequencyTransmitterConsumerEntity(Entity):
    """Base entity for integrations that send commands via an RF transmitter.

    Tracks the availability of the underlying RF transmitter entity.
    """

    _attr_should_poll = False
    # Rename-stable registry ID (or entity_id) of the transmitter, from config.
    _rf_transmitter_entity_id: str
    _rf_unsubscribes: list[CALLBACK_TYPE]

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to RF entity state and rename events."""
        await super().async_added_to_hass()

        self._rf_unsubscribes = []
        self.async_on_remove(self._async_unsubscribe_rf)
        self._async_track_rf_entity(
            er.async_validate_entity_id(
                er.async_get(self.hass), self._rf_transmitter_entity_id
            )
        )

    @callback
    def _async_unsubscribe_rf(self) -> None:
        """Tear down the current transmitter subscriptions."""
        while self._rf_unsubscribes:
            self._rf_unsubscribes.pop()()

    @callback
    def _async_track_rf_entity(self, entity_id: str) -> None:
        """Track state and rename events for the resolved transmitter entity_id."""
        self._async_unsubscribe_rf()
        self._rf_unsubscribes.append(
            async_track_state_change_event(
                self.hass, [entity_id], self._async_rf_state_changed
            )
        )
        self._rf_unsubscribes.append(
            async_track_entity_registry_updated_event(
                self.hass, entity_id, self._async_rf_registry_updated
            )
        )
        rf_state = self.hass.states.get(entity_id)
        self._attr_available = (
            rf_state is not None and rf_state.state != STATE_UNAVAILABLE
        )

    async def _send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command through the RF transmitter entity."""
        await async_send_command(
            self.hass, self._rf_transmitter_entity_id, command, context=self._context
        )

    @callback
    def _async_rf_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Re-track the transmitter when it is renamed."""
        data = event.data
        if data["action"] != "update":
            return
        if "entity_id" not in data["changes"]:
            return
        self._async_track_rf_entity(data["entity_id"])
        self.async_write_ha_state()

    @callback
    def _async_rf_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle RF entity state changes."""
        new_state = event.data["new_state"]
        rf_available = new_state is not None and new_state.state != STATE_UNAVAILABLE
        if rf_available != self.available:
            _LOGGER.info(
                "Radio frequency entity %s used by %s is %s",
                event.data["entity_id"],
                self.entity_id,
                "available" if rf_available else "unavailable",
            )

            self._attr_available = rf_available
            self.async_write_ha_state()
