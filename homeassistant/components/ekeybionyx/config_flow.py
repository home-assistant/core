"""Config flow for Ekey Bionyx."""

from collections.abc import Sequence
import json
import logging
import re
import secrets
from typing import Any, NotRequired, TypedDict

import aiohttp
import ekey_bionyxpy
import voluptuous as vol

from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_path as webhook_generate_path,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector

from . import api
from .const import DOMAIN, SCOPE


class EkeyFlowData(TypedDict):
    """Type for Flow Data."""

    system: NotRequired[ekey_bionyxpy.System]
    systems: NotRequired[list[ekey_bionyxpy.System]]


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ekey Bionyx OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize OAuth2FlowHandler."""
        super().__init__()
        self._data: EkeyFlowData = {}

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
        try:
            system_res = await ap.get_systems()
        except aiohttp.ClientResponseError:
            return self.async_abort(reason="cannot_connect")
        system = [s for s in system_res if s.own_system]
        if len(system) == 0:
            return self.async_abort(reason="no_own_systems")
        self._data["systems"] = system
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
        self._data["system"] = [
            s for s in self._data["systems"] if s.system_id == user_input["system"]
        ][0]
        return await self.async_step_webhooks(user_input=None)

    async def async_step_webhooks(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Dialog to setup webhooks."""
        system = self._data["system"]
        await self.async_set_unique_id(system.system_id)
        self._abort_if_unique_id_configured()
        if (
            system.function_webhook_quotas["free"] == 0
            and system.function_webhook_quotas["used"] == 0
        ):
            return self.async_abort(reason="no_availible_webhooks")
        if system.function_webhook_quotas["used"] > 0:
            return await self.async_step_delete_webhooks()
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = {}
            [
                errors.update({webhooks[0]: "invalid_name"})
                for webhooks in user_input.items()
                if webhooks[0] != CONF_URL
                and not re.match(r"^(?![\d\s])[\w\d\u0020\.]*[\w\d]$", webhooks[1])
            ]
            try:
                cv.url(user_input[CONF_URL])
            except vol.Invalid:
                errors[CONF_URL] = "invalid_url"
        if user_input is None or errors:
            data_schema: dict[Any, Any] = {
                vol.Optional(f"webhook{i + 1}"): vol.All(str, vol.Length(max=50))
                for i in range(self._data["system"].function_webhook_quotas["free"])
            }
            data_schema[
                vol.Required(
                    CONF_URL,
                    default=get_url(
                        self.hass,
                        allow_ip=True,
                        prefer_external=False,
                    ),
                )
            ] = str
            return self.async_show_form(
                step_id="webhooks", data_schema=vol.Schema(data_schema), errors=errors
            )
        webhook_data = [
            {"webhook_id": webhook_generate_id(), "name": webhooks[1]}
            for webhooks in user_input.items()
            if webhooks[0] != CONF_URL
        ]
        for webhook in webhook_data:
            webhook.update(auth=secrets.token_hex(32))
            wh_def: ekey_bionyxpy.WebhookData = {
                "integrationName": "Home Assistant",
                "functionName": webhook["name"],
                "locationName": "Home Assistant",
                "definition": {
                    "url": user_input[CONF_URL]
                    + webhook_generate_path(webhook["webhook_id"]),
                    "authentication": {"apiAuthenticationType": "None"},
                    "securityLevel": "AllowHttp",
                    "method": "Post",
                    "body": {
                        "contentType": "application/json",
                        "content": json.dumps({"auth": webhook["auth"]}),
                    },
                },
            }
            webhook.update(ekey_id=(await system.add_webhook(wh_def)).webhook_id)
        return self.async_create_entry(
            title=self._data["system"].system_name,
            data={"webhooks": webhook_data},
        )

    async def async_step_delete_webhooks(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to delete Webhooks."""
        if user_input is None:
            return self.async_show_form(step_id="delete_webhooks")
        for webhook in await self._data["system"].get_webhooks():
            await webhook.delete()
        return self.async_abort(reason="webhook_deletion_requested")
