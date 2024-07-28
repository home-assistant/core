"""Update coordinator for Knocki integration."""

from knocki import Event, KnockiClient, KnockiConnectionError, Trigger

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class KnockiCoordinator(DataUpdateCoordinator[dict[int, Trigger]]):
    """The Knocki coordinator."""

    def __init__(self, hass: HomeAssistant, client: KnockiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
        )
        self.client = client
        self._known_triggers: set[tuple[str, int]] = set()

    async def _async_update_data(self) -> dict[int, Trigger]:
        try:
            triggers = await self.client.get_triggers()
        except KnockiConnectionError as exc:
            raise UpdateFailed from exc
        current_triggers = {
            (trigger.device_id, trigger.details.trigger_id) for trigger in triggers
        }
        removed_triggers = self._known_triggers - current_triggers
        for trigger in removed_triggers:
            self._async_delete_device(trigger)
        self._known_triggers = current_triggers
        return {trigger.details.trigger_id: trigger for trigger in triggers}

    def add_trigger(self, event: Event) -> None:
        """Add a trigger to the coordinator."""
        self.async_set_updated_data(
            {**self.data, event.payload.details.trigger_id: event.payload}
        )
        self._known_triggers.add(
            (event.payload.device_id, event.payload.details.trigger_id)
        )

    @callback
    def _async_delete_device(self, trigger: tuple[str, int]) -> None:
        """Delete a device from the coordinator."""
        device_id, trigger_id = trigger
        entity_registry = er.async_get(self.hass)
        entity_entry = entity_registry.async_get_entity_id(
            EVENT_DOMAIN, DOMAIN, f"{device_id}_{trigger_id}"
        )
        if entity_entry:
            entity_registry.async_remove(entity_entry)
