"""Coordinator for Streamlabs water integration."""
from dataclasses import dataclass
import logging

from streamlabswater.streamlabswater import StreamlabsClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass(slots=True)
class StreamlabsData:
    """Class to hold Streamlabs data."""

    is_away: bool
    daily_usage: float
    monthly_usage: float
    yearly_usage: float


class StreamlabsCoordinator(DataUpdateCoordinator[StreamlabsData]):
    """Coordinator for Streamlabs."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: StreamlabsClient,
        location_id: str,
        location_name: str,
    ) -> None:
        """Coordinator for Streamlabs."""
        super().__init__(hass, logging.getLogger(__name__), name="Streamlabs")
        self.client = client
        self.location_id = location_id
        self.location_name = location_name

    async def _async_update_data(self) -> StreamlabsData:
        return await self.hass.async_add_executor_job(self._update_data)

    def _update_data(self) -> StreamlabsData:
        water_usage = self.client.get_water_usage_summary(self.location_id)
        location = self.client.get_location(self.location_id)
        return StreamlabsData(
            is_away=location["homeAway"] == "away",
            daily_usage=round(water_usage["today"], 1),
            monthly_usage=round(water_usage["thisMonth"], 1),
            yearly_usage=round(water_usage["thisYear"], 1),
        )
