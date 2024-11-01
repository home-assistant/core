"""Config flow for Ekey Bionyx."""

from collections.abc import Sequence
import json
import logging
from typing import Any

import ekey_bionyxpy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector

from . import api
from .const import DOMAIN, LOGGER, SCOPE


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ekey Bionyx OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize OAuth2FlowHandler."""
        super().__init__()
        self._data: dict[str, Any] = {}

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
        self._data["systems"] = system
        self._data["data"] = data
        if len(system) == 1:
            # skipping choose_system since there is only one
            self._data["system"] = system[0]
            return await self.async_step_webhooks(user_input=None)
        return await self.async_step_choose_system(user_input=None)

    async def async_step_choose_system(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Dialog to choose System if multiple systems are present."""
        if user_input is None:
            options: Sequence[SelectOptionDict] = [
                {"value": s.system_id, "label": s.system_name}
                for s in self._data["systems"]
            ]
            data_schema = {vol.Required("system"): SelectSelector({"options": options})}
            return self.async_show_form(
                step_id="choose_system", data_schema=vol.Schema(data_schema)
            )
        await self.async_set_unique_id(user_input["system"])
        self._data["system"] = [
            s for s in self._data["systems"] if s.system_id == user_input["system"]
        ][0]
        self._abort_if_unique_id_configured()
        return await self.async_step_webhooks(user_input=None)

    async def async_step_webhooks(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Dialog to setup webhooks."""
        LOGGER.info(json.dumps(self._data["system"].function_webhook_quotas))
        if user_input is None or user_input == {}:
            # show the form
            return self.async_create_entry(
                title=self._data["system"].system_name,
                data={**self._data["data"]},
            )
        return self.async_create_entry(
            title=self._data["system"].system_name,
            data={**self._data["data"]},
        )
