"""Config flow to add the integration via the UI."""

from collections.abc import Mapping
import logging
from typing import Any

from aioautomower.session import AutomowerSession
from aioautomower.utils import structure_token

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.util import dt as dt_util

from .api import AsyncConfigFlowAuth
from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

CONF_USER_ID = "user_id"
HUSQVARNA_DEV_PORTAL_URL = "https://developer.husqvarnagroup.cloud/applications"


class HusqvarnaConfigFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    VERSION = 1
    DOMAIN = DOMAIN

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        token = data[CONF_TOKEN]
        if "amc:api" not in token["scope"] and self.source != SOURCE_REAUTH:
            return self.async_abort(reason="missing_amc_scope")
        user_id = token[CONF_USER_ID]
        await self.async_set_unique_id(user_id)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            if "amc:api" not in token["scope"]:
                return self.async_update_reload_and_abort(
                    reauth_entry, data=data, reason="missing_amc_scope"
                )
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(reauth_entry, data=data)

        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)
        tz = await dt_util.async_get_time_zone(str(dt_util.DEFAULT_TIME_ZONE))
        automower_api = AutomowerSession(AsyncConfigFlowAuth(websession, token), tz)
        try:
            status_data = await automower_api.get_status()
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="unknown")
        if status_data == {}:
            return self.async_abort(reason="no_mower_connected")

        structured_token = structure_token(token[CONF_ACCESS_TOKEN])
        first_name = structured_token.user.first_name
        last_name = structured_token.user.last_name

        return self.async_create_entry(
            title=f"{NAME} of {first_name} {last_name}",
            data=data,
        )

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        if "amc:api" not in entry_data["token"]["scope"]:
            return await self.async_step_missing_scope()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={CONF_NAME: self._get_reauth_entry().title},
            )
        return await self.async_step_user()

    async def async_step_missing_scope(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth for missing scope."""
        if user_input is None and self.source == SOURCE_REAUTH:
            token_structured = structure_token(
                self._get_reauth_entry().data["token"]["access_token"]
            )
            return self.async_show_form(
                step_id="missing_scope",
                description_placeholders={
                    "application_url": f"{HUSQVARNA_DEV_PORTAL_URL}/{token_structured.client_id}"
                },
            )
        return await self.async_step_user()
