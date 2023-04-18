"""Data update coordinator for the LastFM integration."""
from pylast import LastFMNetwork, User, WSError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_USERS, DOMAIN, LOGGER


class LastFmUpdateCoordinator(DataUpdateCoordinator[dict[str, User]]):
    """Data update coordinator for the LastFM integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(hass=hass, logger=LOGGER, name=DOMAIN)

        self.lastfm_api = LastFMNetwork(api_key=self.config_entry.data[CONF_API_KEY])

    def _update(self) -> dict[str, User]:
        users = self.config_entry.data[CONF_USERS]
        response = {}
        for user in users:
            try:
                response[user] = self.lastfm_api.get_user(user)
            except WSError as error:
                LOGGER.error(error)
        return response

    async def _async_update_data(self) -> dict[str, User]:
        """Send request to the executor."""
        return await self.hass.async_add_executor_job(self._update)
