"""Helper classes and functions for the Legrand Home+ Control integration."""
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONF_SUBSCRIPTION_KEY, DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN


class HomePlusControlOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """OAuth2 implementation that extends the HomeAssistant local implementation.

    It provides the name of the integration and adds support for the subscription key.

    Attributes:
        hass (HomeAssistant): HomeAssistant core object.
        client_id (str): Client identifier assigned by the API provider when registering an app.
        client_secret (str): Client secret assigned by the API provider when registering an app.
        subscription_key (str): Subscription key obtained from the API provider.
        authorize_url (str): Authorization URL initiate authentication flow.
        token_url (str): URL to retrieve access/refresh tokens.
        name (str): Name of the implementation (appears in the HomeAssitant GUI).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_data: dict,
    ):
        """HomePlusControlOAuth2Implementation Constructor.

            Initialize the authentication implementation for the Legrand Home+ Control API.

        Args:
            hass (HomeAssistant): HomeAssistant core object.
            config_data (dict): Configuration data that complies with the config Schema
                                of this component.
        """
        super().__init__(
            hass=hass,
            domain=DOMAIN,
            client_id=config_data[CONF_CLIENT_ID],
            client_secret=config_data[CONF_CLIENT_SECRET],
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )
        self.subscription_key = config_data[CONF_SUBSCRIPTION_KEY]

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Home+ Control"
