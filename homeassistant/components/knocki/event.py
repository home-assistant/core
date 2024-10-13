"""Event entity for Knocki integration."""

from knocki import Event, EventType, KnockiClient, Trigger

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KnockiConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KnockiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Knocki from a config entry."""
    coordinator = entry.runtime_data

    added_triggers = set(coordinator.data)

    @callback
    def _async_add_entities() -> None:
        current_triggers = set(coordinator.data)
        new_triggers = current_triggers - added_triggers
        added_triggers.update(new_triggers)
        if new_triggers:
            async_add_entities(
                KnockiTrigger(coordinator.data[trigger], coordinator.client)
                for trigger in new_triggers
            )

    coordinator.async_add_listener(_async_add_entities)

    async_add_entities(
        KnockiTrigger(trigger, coordinator.client)
        for trigger in coordinator.data.values()
    )


EVENT_TRIGGERED = "triggered"


class KnockiTrigger(EventEntity):
    """Representation of a Knocki trigger."""

    _attr_event_types = [EVENT_TRIGGERED]
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "knocki"

    def __init__(self, trigger: Trigger, client: KnockiClient) -> None:
        """Initialize the entity."""
        self._trigger = trigger
        self._client = client
        self._attr_name = trigger.details.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, trigger.device_id)},
            manufacturer="Knocki",
            serial_number=trigger.device_id,
            name=trigger.device_id,
        )
        self._attr_unique_id = f"{trigger.device_id}_{trigger.details.trigger_id}"

    async def async_added_to_hass(self) -> None:
        """Register listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._client.register_listener(EventType.TRIGGERED, self._handle_event)
        )

    def _handle_event(self, event: Event) -> None:
        """Handle incoming event."""
        if (
            event.payload.details.trigger_id == self._trigger.details.trigger_id
            and event.payload.device_id == self._trigger.device_id
        ):
            self._trigger_event(EVENT_TRIGGERED)
            self.schedule_update_ha_state()
