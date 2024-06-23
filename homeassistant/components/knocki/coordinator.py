"""Update coordinator for Knocki integration."""
from knocki import Trigger, KnockiConnectionError

from homeassistant.components.knocki.const import LOGGER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


class KnockiCoordinator(DataUpdateCoordinator[dict[str, Trigger]]):

    def __init__(self, hass: HomeAssistant, client: KnockiClient):
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
        )

    async def _async_update_data(self) -> dict[str, Trigger]:
        """Fetch data from API endpoint."""
        try:
            return await self.client.get_triggers()
        except KnockiConnectionError as exc:
            raise UpdateFailed from exc