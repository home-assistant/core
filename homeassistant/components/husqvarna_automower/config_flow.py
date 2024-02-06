"""Config flow to add the integration via the UI."""
import logging
from typing import Any

from aioautomower.utils import async_structure_token

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)
CONF_USER_ID = "user_id"


class HusqvarnaConfigFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    VERSION = 1
    DOMAIN = DOMAIN

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow."""
        token = data[CONF_TOKEN]
        user_id = token[CONF_USER_ID]
        structured_token = await async_structure_token(token[CONF_ACCESS_TOKEN])
        first_name = structured_token.user.first_name
        last_name = structured_token.user.last_name
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{NAME} of {first_name} {last_name}",
            data=data,
        )

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
