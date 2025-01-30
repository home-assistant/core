import logging
import aiohttp
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN, API_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the light platform."""
    access_token = config_entry.data.get("access_token")
    if access_token:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{API_URL}/home_assistant?access_token={access_token}') as response:
                    if response.status == 200:
                        data = await response.json()
                        entities = []
                        for item in data.get("boards", []):
                            categories = item.get("displayCategories", "")
                            if "SWITCH" in categories:
                                
                                entities.append(RedgtechSwitch(item, access_token))
                        async_add_entities(entities)
                    else:
                        _LOGGER.error("Error fetching data from API: %s", response.status)
        except aiohttp.ClientError as e:
            _LOGGER.error("Error connecting to API: %s", e)
    else:
        _LOGGER.error("No access token available")

class RedgtechSwitch(SwitchEntity):
    """Representation of a Redgtech switch."""

    def __init__(self, data, token):
        self._state = data.get("value", False)
        self._name = data.get("friendlyName")
        self._endpoint_id = data.get("endpointId")
        self._description = data.get("description")
        self._manufacturer = data.get("manufacturerName")
        self._token = token

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._set_state(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._set_state(False)

    async def _set_state(self, state):
        """Send the state to the API to update the switch."""
        id_part, after_id = self._endpoint_id.split("-", 1)
        value = ''.join(filter(str.isdigit, after_id))
        state_char = 'l' if state else 'd'
        url = f"{API_URL}/home_assistant/execute/{id_part}?cod=?{value}{state_char}"
        headers = {"Authorization": f"{self._token}"}
        payload = {"state": state}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    self._state = state
                    self.async_write_ha_state()
                else:
                    _LOGGER.error("Failed to set state for %s, status code: %s", self._name, response.status)

    async def async_update(self):
        """Get the latest state of the switch."""
        id_part, after_id = self._endpoint_id.split("-", 1)
        value = after_id
        url = f"{API_URL}/home_assistant?access_token={self._token}"
        headers = {"Authorization": f"{self._token}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        for board in data.get("boards", []):
                            if board.get("endpointId") == self._endpoint_id:
                                value = board.get("value", False)
                                self._state = bool(value)
                                self.async_write_ha_state()
                                break
                    else:
                        _LOGGER.error(
                            "Failed to update state for %s, status code: %s",
                            self._name,
                            response.status,
                        )
        except Exception as e:
            _LOGGER.error("Error updating state for %s: %s", self._name, str(e))