"""API for Legrand Home+ Control bound to Home Assistant OAuth."""
from homepluscontrol.homeplusapi import HomePlusControlAPI

from homeassistant import config_entries, core
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import DEFAULT_UPDATE_INTERVALS
from .helpers import HomePlusControlOAuth2Implementation


class HomePlusControlAsyncApi(HomePlusControlAPI):
    """Legrand Home+ Control object that interacts with the OAuth2-based API of the provider.

    This API is bound the HomeAssistant Config Entry that corresponds to this component.

    Attributes:.
        hass (HomeAssistant): HomeAssistant core object.
        config_entry (ConfigEntry): ConfigEntry object that configures this API.
        implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA and
                                                       token refresh.
        _oauth_session (OAuth2Session): OAuth2Session object within implementation.
    """

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ) -> None:
        """Initialize the HomePlusControlAsyncApi object.

        Initialize the authenticated API for the Legrand Home+ Control component.

        Args:.
            hass (HomeAssistant): HomeAssistant core object.
            config_entry (ConfigEntry): ConfigEntry object that configures this API.
            implementation (AbstractOAuth2Implementation): OAuth2 implementation that handles AA
                                                           and token refresh.
        """
        self._oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )

        assert isinstance(implementation, HomePlusControlOAuth2Implementation)

        # Create the API authenticated client - external library
        super().__init__(
            subscription_key=implementation.subscription_key,
            oauth_client=aiohttp_client.async_get_clientsession(hass),
            update_intervals=DEFAULT_UPDATE_INTERVALS,
        )

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
