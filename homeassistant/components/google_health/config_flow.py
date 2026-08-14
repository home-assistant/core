"""Config flow for Google Health."""

from collections.abc import Mapping
import logging
from typing import Any, override

from google_health_api import GoogleHealthApi
from google_health_api.const import HealthApiScope
from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
)

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .api import SimpleAuth
from .const import API_CONSOLE_URL, DEFAULT_TITLE, DOMAIN, OAUTH_SCOPES

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        return await self.async_step_user(user_input)

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        scopes = data.get(CONF_TOKEN, {}).get("scope", "").split()
        if HealthApiScope.PROFILE_READ not in scopes:
            return self.async_abort(reason="missing_profile_scope")

        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        websession = aiohttp_client.async_get_clientsession(self.hass)
        auth = SimpleAuth(websession, access_token)
        api = GoogleHealthApi(auth)

        try:
            identity = await api.get_identity()
        except HealthApiForbiddenException as err:
            _LOGGER.error("Error getting Google Health identity: %s", err)
            return self.async_abort(
                reason="api_not_enabled",
                description_placeholders={"url": API_CONSOLE_URL},
            )
        except GoogleHealthApiError as err:
            _LOGGER.error("Error getting Google Health identity: %s", err)
            return self.async_abort(reason="cannot_connect")

        if not identity.health_user_id:
            _LOGGER.error("Google Health identity has no health_user_id")
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(identity.health_user_id)
        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            if self.source == SOURCE_REAUTH:
                entry = self._get_reauth_entry()
            else:
                entry = self._get_reconfigure_entry()
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(entry, data=data)
        self._abort_if_unique_id_configured()

        display_name = None
        if HealthApiScope.USERINFO_PROFILE in scopes or "profile" in scopes:
            try:
                userinfo = await api.get_user_info()
                display_name = userinfo.given_name or userinfo.name
            except Exception as err:  # pylint: disable=broad-except # noqa: BLE001
                _LOGGER.warning("Error fetching user profile name: %s", err)

        return self.async_create_entry(
            title=display_name or DEFAULT_TITLE,
            data=data,
        )
