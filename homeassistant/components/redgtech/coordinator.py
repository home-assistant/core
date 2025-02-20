import logging
from datetime import timedelta
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from redgtech_api import RedgtechAPI
from .const import DOMAIN
from typing import List

_LOGGER = logging.getLogger(__name__)

class RedgtechDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass, api: RedgtechAPI):
        """Initialize."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=1),
        )

    async def _async_update_data(self) -> List[dict]:
        """Fetch data from API."""
        try:
            _LOGGER.debug("Fetching data from Redgtech API")
            data = await self.api.get_data()
            entities = []
            for item in data.get("boards", []):
                entity_id = item.get('endpointId', '')
                entity_name = item.get("friendlyName", '')
                entity_value = item.get("value", False)
                entity_state = STATE_ON if entity_value else STATE_OFF
                _LOGGER.debug("Processing entity: id=%s, name=%s, value=%s, state=%s", entity_id, entity_name, entity_value, entity_state)

                entities.append({
                    "id": entity_id,
                    "name": entity_name,
                    "state": entity_state,
                    "type": 'switch'
                })
            return entities
        except Exception as e:
            raise UpdateFailed(f"Error fetching data: {e}")