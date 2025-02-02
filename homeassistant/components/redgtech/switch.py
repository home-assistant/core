import logging
from homeassistant.components.switch import SwitchEntity
from redgtech_api import RedgtechAPI
from .const import DOMAIN, API_URL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    access_token = config_entry.data.get("access_token")
    if access_token:
        api = RedgtechAPI(access_token)
        try:
            data = await api.get_data()
            entities = []
            for item in data.get("boards", []):
                categories = item.get("displayCategories", "")
                if "SWITCH" in categories:
                    entities.append(RedgtechSwitch(item, api))
            async_add_entities(entities)
        except Exception as e:
            _LOGGER.error("Error fetching data from API: %s", e)
    else:
        _LOGGER.error("No access token available")

class RedgtechSwitch(SwitchEntity):
    """Representation of a Redgtech switch."""

    def __init__(self, data, api):
        self._state = data.get("value", False)
        self._name = data.get("friendlyName")
        self._endpoint_id = data.get("endpointId")
        self._description = data.get("description")
        self._manufacturer = data.get("manufacturerName")
        self._api = api

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
        success = await self._api.set_switch_state(self._endpoint_id, state)
        if success:
            self._state = state
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set state for %s", self._name)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "endpoint_id": self._endpoint_id,
            "description": self._description,
            "manufacturer": self._manufacturer,
        }