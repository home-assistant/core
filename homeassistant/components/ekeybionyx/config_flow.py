"""Config flow for Ekey Bionyx."""

import logging
from typing import Any

import ekey_bionyxpy

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import api
from .const import DOMAIN, SCOPE


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ekey Bionyx OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPE}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        client = api.ConfigFlowEkeyApi(
            async_get_clientsession(self.hass), data[CONF_TOKEN]
        )
        ap = ekey_bionyxpy.BionyxAPI(client)
        system = [s for s in await ap.get_systems() if s.own_system]
        if len(system) == 0:
            return self.async_abort(reason="no_own_systems")

        return self.async_create_entry(
            title=system[0].system_name,
            data={**data},
        )
