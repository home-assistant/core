"""Config flow for Google Health."""

from collections.abc import Mapping
import logging
from typing import Any, override

from google_health_api import GoogleHealthApi
from google_health_api.exceptions import GoogleHealthApiError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .api import SimpleAuth
from .const import DOMAIN, OAUTH_SCOPES

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Health OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
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

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        websession = aiohttp_client.async_get_clientsession(self.hass)
        auth = SimpleAuth(websession, access_token)
        api = GoogleHealthApi(auth)

        try:
            identity = await api.get_identity()
        except GoogleHealthApiError as err:
            _LOGGER.error("Error getting Google Health identity: %s", err)
            return self.async_abort(reason="cannot_connect")

        if not identity.health_user_id:
            _LOGGER.error("Google Health identity has no health_user_id")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(identity.health_user_id)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(reauth_entry, data=data)

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=identity.name or "Google Health",
            data=data,
        )
