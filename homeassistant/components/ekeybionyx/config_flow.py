"""Config flow for ekey bionyx."""

import asyncio
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

from .const import API_URL, DOMAIN, SCOPE

# Valid webhook name: starts with letter or underscore, contains letters, digits, spaces, dots, and underscores, does not end with space or dot
VALID_NAME_PATTERN = re.compile(r"^(?![\d\s])[\w\d \.]*[\w\d]$")


class ConfigFlowEkeyApi(ekey_bionyxpy.AbstractAuth):
    """Ekey Bionyx authentication before a ConfigEntry exists.

    This implementation directly provides the token without supporting refresh.
    """

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        token: dict[str, Any],
    ) -> None:
        """Initialize ConfigFlowEkeyApi."""
        super().__init__(websession, API_URL)
        self._token = token

    async def async_get_access_token(self) -> str:
        """Return the token for the Ekey API."""
        return self._token["access_token"]


class EkeyFlowData(TypedDict):
    """Type for Flow Data."""

    api: NotRequired[ekey_bionyxpy.BionyxAPI]
    system: NotRequired[ekey_bionyxpy.System]
    systems: NotRequired[list[ekey_bionyxpy.System]]


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ekey Bionyx OAuth2 authentication."""

    DOMAIN = DOMAIN

    check_deletion_task: asyncio.Task[None] | None = None

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
        """Start the user facing flow by initializing the API and getting the systems."""
        client = ConfigFlowEkeyApi(async_get_clientsession(self.hass), data[CONF_TOKEN])
        ap = ekey_bionyxpy.BionyxAPI(client)
        self._data["api"] = ap
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
            return await self.async_step_check_system(user_input=None)
        return await self.async_step_choose_system(user_input=None)

    async def async_step_choose_system(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Dialog to choose System if multiple systems are present."""
        if user_input is None:
            options: list[SelectOptionDict] = [
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
        return await self.async_step_check_system(user_input=None)

    async def async_step_check_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check if system has open webhooks."""
        system = self._data["system"]
        await self.async_set_unique_id(system.system_id)
        self._abort_if_unique_id_configured()

        if (
            system.function_webhook_quotas["free"] == 0
            and system.function_webhook_quotas["used"] == 0
        ):
            return self.async_abort(reason="no_available_webhooks")

        if system.function_webhook_quotas["used"] > 0:
            return await self.async_step_delete_webhooks()
        return await self.async_step_webhooks(user_input=None)

    async def async_step_webhooks(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Dialog to setup webhooks."""
        system = self._data["system"]

        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = {}
            for key, webhook_name in user_input.items():
                if key == CONF_URL:
                    continue
                if not re.match(VALID_NAME_PATTERN, webhook_name):
                    errors.update({key: "invalid_name"})
            try:
                cv.url(user_input[CONF_URL])
            except vol.Invalid:
                errors[CONF_URL] = "invalid_url"
            if set(user_input) == {CONF_URL}:
                errors["base"] = "no_webhooks_provided"

            if not errors:
                webhook_data = [
                    {
                        "auth": secrets.token_hex(32),
                        "name": webhooks[1],
                        "webhook_id": webhook_generate_id(),
                    }
                    for webhooks in user_input.items()
                    if webhooks[0] != CONF_URL
                ]
                for webhook in webhook_data:
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
                    webhook["ekey_id"] = (await system.add_webhook(wh_def)).webhook_id
                return self.async_create_entry(
                    title=self._data["system"].system_name,
                    data={"webhooks": webhook_data},
                )

        data_schema: dict[Any, Any] = {
            vol.Optional(f"webhook{i + 1}"): vol.All(str, vol.Length(max=50))
            for i in range(self._data["system"].function_webhook_quotas["free"])
        }
        data_schema[vol.Required(CONF_URL)] = str
        return self.async_show_form(
            step_id="webhooks",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(data_schema),
                {
                    CONF_URL: get_url(
                        self.hass,
                        allow_ip=True,
                        prefer_external=False,
                    )
                }
                | (user_input or {}),
            ),
            errors=errors,
        )

    async def async_step_delete_webhooks(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to delete Webhooks."""
        if user_input is None:
            return self.async_show_form(step_id="delete_webhooks")
        for webhook in await self._data["system"].get_webhooks():
            await webhook.delete()
        return await self.async_step_wait_for_deletion(user_input=None)

    async def async_step_wait_for_deletion(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for webhooks to be deleted in another flow."""
        uncompleted_task: asyncio.Task[None] | None = None

        if not self.check_deletion_task:
            self.check_deletion_task = self.hass.async_create_task(
                self.async_check_deletion_status()
            )
        if not self.check_deletion_task.done():
            progress_action = "check_deletion_status"
            uncompleted_task = self.check_deletion_task
        if uncompleted_task:
            return self.async_show_progress(
                step_id="wait_for_deletion",
                progress_action=progress_action,
                progress_task=uncompleted_task,
            )
        self.check_deletion_task = None
        return self.async_show_progress_done(next_step_id="webhooks")

    async def async_check_deletion_status(self) -> None:
        """Check if webhooks have been deleted."""
        while True:
            self._data["systems"] = await self._data["api"].get_systems()
            self._data["system"] = [
                s
                for s in self._data["systems"]
                if s.system_id == self._data["system"].system_id
            ][0]
            if self._data["system"].function_webhook_quotas["used"] == 0:
                break
            await asyncio.sleep(5)
