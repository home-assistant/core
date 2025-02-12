"""Config flow to configure SmartThings."""

from collections.abc import Mapping
import logging
from typing import Any

from pysmartthings import SmartThings

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_INSTALLED_APP_ID, CONF_LOCATION_ID, DOMAIN, SCOPES

_LOGGER = logging.getLogger(__name__)


class SmartThingsConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 3
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for SmartThings."""
        client = SmartThings(session=async_get_clientsession(self.hass))
        client.authenticate(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        locations = await client.get_locations()
        location = locations[0]
        await self.async_set_unique_id(data[CONF_TOKEN][CONF_INSTALLED_APP_ID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=location.name, data={**data, CONF_LOCATION_ID: location.location_id}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )
        return await self.async_step_user()
