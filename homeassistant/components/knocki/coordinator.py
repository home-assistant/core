"""Update coordinator for Knocki integration."""

from knocki import Event, KnockiClient, KnockiConnectionError, Trigger

from homeassistant.core import HomeAssistant
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

    async def _async_update_data(self) -> dict[int, Trigger]:
        try:
            triggers = await self.client.get_triggers()
        except KnockiConnectionError as exc:
            raise UpdateFailed from exc
        return {trigger.details.trigger_id: trigger for trigger in triggers}

    def add_trigger(self, event: Event) -> None:
        """Add a trigger to the coordinator."""
        self.async_set_updated_data(
            {**self.data, event.payload.details.trigger_id: event.payload}
        )
