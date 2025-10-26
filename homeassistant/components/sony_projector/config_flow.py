"""Config flow for the Sony Projector integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .client import ProjectorClient, ProjectorClientError
from .const import CONF_TITLE, DEFAULT_NAME, DOMAIN


class SonyProjectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sony Projector."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            name = user_input.get(CONF_NAME)

            client = ProjectorClient(host)
            try:
                await client.async_validate_connection()
            except ProjectorClientError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host, raise_on_progress=False)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                title = name or DEFAULT_NAME
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_TITLE: title,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_data_schema(user_input),
            errors=errors,
        )

    async def async_step_import(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle YAML import."""

        host = user_input[CONF_HOST]
        name = user_input.get(CONF_NAME)

        client = ProjectorClient(host)
        try:
            await client.async_validate_connection()
        except ProjectorClientError:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(host, raise_on_progress=False)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        title = name or DEFAULT_NAME
        return self.async_create_entry(
            title=title,
            data={
                CONF_HOST: host,
                CONF_TITLE: title,
            },
        )

    def _user_data_schema(self, user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Return the data schema for the user form."""

        user_input = user_input or {}

        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "")): str,
            }
        )
