"""Demo platform that offers a fake infrared receiver event entity."""

from homeassistant.components.event import EventEntity
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_subscribe_receiver,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_INFRARED_RECEIVER_ENTITY_ID, DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo infrared event platform."""
    for subentry_id, subentry in config_entry.subentries.items():
        if subentry.subentry_type != "infrared_fan":
            continue
        if subentry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID) is None:
            continue
        async_add_entities(
            [
                DemoInfraredEvent(
                    subentry_id=subentry_id,
                    device_name=subentry.title,
                    infrared_receiver_entity_id=subentry.data[
                        CONF_INFRARED_RECEIVER_ENTITY_ID
                    ],
                )
            ],
            config_subentry_id=subentry_id,
        )


class DemoInfraredEvent(EventEntity):
    """Representation of a demo infrared event entity."""

    _attr_has_entity_name = True
    _attr_name = "Received IR Event"
    _attr_should_poll = False
    _attr_event_types = ["unknown"]

    def __init__(
        self, subentry_id: str, device_name: str, infrared_receiver_entity_id: str
    ) -> None:
        """Initialize the demo infrared event entity."""
        self._receiver_entity_id = infrared_receiver_entity_id
        self._attr_unique_id = subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)}, name=device_name
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to the IR receiver when added to hass."""
        await super().async_added_to_hass()

        @callback
        def _handle_signal(signal: InfraredReceivedSignal) -> None:
            """Handle a received IR signal."""
            self._trigger_event("unknown", {"raw_code": signal.timings})
            self.async_write_ha_state()

        remove_signal_subscription: CALLBACK_TYPE | None = None

        @callback
        def _async_unsubscribe_receiver() -> None:
            """Unsubscribe from the current IR receiver."""
            nonlocal remove_signal_subscription

            if remove_signal_subscription is None:
                return
            remove_signal_subscription()
            remove_signal_subscription = None

        @callback
        def _async_update_receiver_subscription(write_state: bool = True) -> None:
            """Update the IR receiver subscription when availability changes."""
            nonlocal remove_signal_subscription

            ir_state = self.hass.states.get(self._receiver_entity_id)
            receiver_available = (
                ir_state is not None and ir_state.state != STATE_UNAVAILABLE
            )

            if not receiver_available:
                _async_unsubscribe_receiver()
            elif remove_signal_subscription is None:
                remove_signal_subscription = async_subscribe_receiver(
                    self.hass, self._receiver_entity_id, _handle_signal
                )

            if self._attr_available == receiver_available:
                return

            self._attr_available = receiver_available
            if write_state:
                self.async_write_ha_state()

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle infrared entity state changes."""
            _async_update_receiver_subscription()

        _async_update_receiver_subscription(write_state=False)
        self.async_on_remove(_async_unsubscribe_receiver)
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._receiver_entity_id], _async_ir_state_changed
            )
        )
