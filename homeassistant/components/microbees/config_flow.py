"""Config flow for microBees integration."""
from collections.abc import Mapping
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_flow as cv,
    config_entry_oauth2_flow,
)

from .api import get_api_scopes
from .const import DOMAIN, VERSION
from .microbees import MicroBeesConnector

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for microBees."""

    CONFIG_SCHEMA = cv.config_entry_only_config_schema
    DOMAIN = DOMAIN
    VERSION = VERSION

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = get_api_scopes(self.flow_impl.domain)
        return {"scope": " ".join(scopes)}

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        microBees = MicroBeesConnector(
            session=aiohttp_client.async_get_clientsession(self.hass),
            token=data["token"]["access_token"],
        )

        current_user = await microBees.getMyProfile()

        data["id"] = current_user.id

        name = current_user.firstName + " " + current_user.lastName
        data["name"] = name

        await self.async_set_unique_id(current_user.id)

        return self.async_create_entry(title=name, data=data)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow start."""
        await self.async_set_unique_id(DOMAIN)

        if (
            self.source != config_entries.SOURCE_REAUTH
            and self._async_current_entries()
        ):
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema={}, errors={}
            )
        return await self.async_step_user()
