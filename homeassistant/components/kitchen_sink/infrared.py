"""Demo platform that offers a fake infrared entity."""

from infrared_protocols.commands import Command as InfraredCommand

from homeassistant.components import persistent_notification
from homeassistant.components.infrared import (
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

PARALLEL_UPDATES = 0

INFRARED_COMMAND_SIGNAL = f"{DOMAIN}_infrared_command_signal"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared platform."""
    async_add_entities(
        [
            DemoInfraredEmitter(
                unique_id="ir_emitter",
                entity_name="Infrared Emitter",
            ),
            DemoInfraredReceiver(
                unique_id="ir_receiver",
                entity_name="Infrared Receiver",
            ),
        ]
    )


# pylint: disable=home-assistant-enforce-class-module
class DemoInfraredEntityBase(Entity):
    """Representation of a demo infrared entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_name: str) -> None:
        """Initialize the demo infrared entity."""
        super().__init__()
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "infrared")}, name="IR Blaster"
        )
        self._attr_name = entity_name


class DemoInfraredEmitter(DemoInfraredEntityBase, InfraredEmitterEntity):
    """Representation of a demo infrared emitter entity."""

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command."""
        raw_timings = command.get_raw_timings()
        persistent_notification.async_create(
            self.hass, str(raw_timings), title="Infrared Command Sent"
        )
        async_dispatcher_send(self.hass, INFRARED_COMMAND_SIGNAL, raw_timings)


class DemoInfraredReceiver(DemoInfraredEntityBase, InfraredReceiverEntity):
    """Representation of a demo infrared receiver entity."""

    @callback
    def _on_dispatcher_signal(self, raw_timings: list[int]) -> None:
        """Handle received infrared command signal."""
        self._handle_received_signal(InfraredReceivedSignal(timings=raw_timings))

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, INFRARED_COMMAND_SIGNAL, self._on_dispatcher_signal
            )
        )
