import logging
from datetime import timedelta
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from redgtech_api import RedgtechAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the switch platform."""
    access_token = config_entry.data.get("access_token")
    if not access_token:
        _LOGGER.error("No access token available")
        return

    api = RedgtechAPI(access_token)
    coordinator = RedgtechDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    if coordinator.data:
        for item in coordinator.data.get("boards", []):
            categories = item.get("displayCategories", "")
            if "SWITCH" in categories:
                entities.append(RedgtechSwitch(coordinator, item, api))

    async_add_entities(entities)

class RedgtechDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass, api):
        """Initialize."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=1),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            _LOGGER.debug("Fetching data from Redgtech API")
            return await self.api.get_data()
        except Exception as e:
            raise UpdateFailed(f"Error fetching data: {e}")

class RedgtechSwitch(SwitchEntity):
    """Representation of a Redgtech switch."""

    def __init__(self, coordinator, data, api):
        """Initialize the switch."""
        self.coordinator = coordinator
        self.api = api
        self._state = data.get("value", False)
        self._name = data.get("friendlyName")
        self._endpoint_id = data.get("endpointId")

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
        """Send the state to the API and update immediately."""
        _LOGGER.debug("Setting state of %s to %s", self._name, state)

        success = await self.api.set_switch_state(self._endpoint_id, state)
        if success:
            self._state = state
            self.async_write_ha_state()
            _LOGGER.debug("State of %s set to %s", self._name, state)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set state for %s", self._name)

    async def async_update(self):
        """Fetch new state data for the switch."""
        _LOGGER.debug("Updating switch state: %s", self._name)
        await self.coordinator.async_request_refresh()
        data = self.coordinator.data
        if data:
            for item in data.get("boards", []):
                if item.get("endpointId") == self._endpoint_id:
                    self._state = item.get("value", False)
                    self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "endpoint_id": self._endpoint_id,
        }
