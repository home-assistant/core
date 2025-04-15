"""Config flow for fitbit."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import DOMAIN, OAUTH_SCOPES
from .exceptions import FitbitApiException, FitbitAuthException

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle fitbit OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH_SCOPES),
            "prompt": "consent" if self.source != SOURCE_REAUTH else "none",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create config entry from external data with Fitbit specific error handling."""
        try:
            return await super().async_step_creation()
        except FitbitAuthException as err:
            _LOGGER.error(
                "Failed to authenticate when creating Fitbit credentials: %s", err
            )
            return self.async_abort(reason="invalid_auth")
        except FitbitApiException as err:
            _LOGGER.error("Failed to create Fitbit credentials: %s", err)
            return self.async_abort(reason="cannot_connect")

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""

        client = api.ConfigFlowFitbitApi(self.hass, data[CONF_TOKEN])
        try:
            profile = await client.async_get_user_profile()
        except FitbitAuthException as err:
            _LOGGER.error("Failed to authenticate with Fitbit API: %s", err)
            return self.async_abort(reason="invalid_access_token")
        except FitbitApiException as err:
            _LOGGER.error("Failed to fetch user profile for Fitbit API: %s", err)
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(profile.encoded_id)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=profile.display_name, data=data)
