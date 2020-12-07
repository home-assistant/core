"""API for Legrand Home+ Control bound to Home Assistant OAuth."""
import logging

from homepluscontrol.authentication import HomePlusOAuth2Async
from homepluscontrol.homeplusinteractivemodule import HomePlusInteractiveModule
from homepluscontrol.homeplusplant import HomePlusPlant

from homeassistant import config_entries, core
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_REDIRECT_URI, CONF_SUBSCRIPTION_KEY, PLANT_URL


class HomePlusControlAsyncApi(HomePlusOAuth2Async):
    """Legrand Home+ Control object that interacts with the OAuth2-based API of the provider.

    This API is bound the HomeAssistant Config Entry that corresponds to this component.

    Attributes:.
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this API.
        implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA and token refresh.
        logger (Logger): Logger of the object.
    """

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize the HomePlusControlAsyncApi object.

        Initialize the authenticated API for the Legrand Home+ Control component.

        Args:.
            hass (HomeAssistant): HomeAssistant core object.
            config_entry (ConfigEntry): ConfigEntry object that configures this API.
            implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA and token refresh.
        """
        self.hass = hass
        self.config_entry = config_entry
        self.implementation = implementation

        # Create the API authenticated client - external library
        super().__init__(
            client_id=self.config_entry.data[CONF_CLIENT_ID],
            client_secret=self.config_entry.data[CONF_CLIENT_SECRET],
            subscription_key=self.config_entry.data[CONF_SUBSCRIPTION_KEY],
            redirect_uri=self.config_entry.data[CONF_REDIRECT_URI],
            token=self.config_entry.data["token"],
        )

    @property
    def logger(self) -> logging.Logger:
        """Logger of authentication API."""
        return logging.getLogger(__name__)

    async def async_ensure_token_valid(self) -> None:
        """Ensure that the current token is valid.

        Overrides the method of the external library to ensure that we update the
        config entry whenever the token is refreshed.
        """
        if self.valid_token:
            self.logger.debug("Legrand Home+ Control oauth token is still valid.")
            return

        self.logger.debug(
            "Legrand Home+ Control oauth token is no longer valid so refreshing."
        )
        new_token = await self.implementation.async_refresh_token(self.token)
        self.token = new_token

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "token": new_token}
        )

    async def fetch_data(self):
        """Get the latest data from the API.

        Return:
            Array of switch entities in their updated state.
        """
        result = await self.get_request(PLANT_URL)
        plant_info = await result.json()
        self.logger.debug(f"Obtained plant information: {plant_info}")
        plant_array = []
        for p in plant_info["plants"]:
            plant_array.append(HomePlusPlant(p["id"], p["name"], p["country"], self))

        plant = plant_array[0]
        await plant.update_topology_and_modules()
        switches = []
        for module in list(plant.modules.values()):
            if isinstance(module, HomePlusInteractiveModule):
                self.logger.debug(f"Including Home+ Control module: {str(module)}")
                switches.append(module)
            else:
                self.logger.debug(f"Ignoring Home+ Control module: {str(module)}")
        return switches

    async def close_connection(self):
        """Clean up the connection."""
        await self.oauth_client.close()
