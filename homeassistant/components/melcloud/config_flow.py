"""Config flow for the MELCloud platform."""
from __future__ import annotations

import asyncio
from http import HTTPStatus

from aiohttp import ClientError, ClientResponseError
import pymelcloud
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN


async def async_create_import_issue(
    hass: HomeAssistant, source: str, issue: str, success: bool = False
) -> None:
    """Create issue from import."""
    if source != config_entries.SOURCE_IMPORT:
        return
    if not success:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{issue}",
            breaks_in_ha_version="2024.2.0",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key=f"deprecated_yaml_import_issue_{issue}",
        )
        return
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "MELCloud",
        },
    )


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _create_entry(self, username: str, token: str):
        """Register new entry."""
        await self.async_set_unique_id(username)
        try:
            self._abort_if_unique_id_configured({CONF_TOKEN: token})
        except AbortFlow:
            await async_create_import_issue(self.hass, self.context["source"], "", True)
            raise
        return self.async_create_entry(
            title=username, data={CONF_USERNAME: username, CONF_TOKEN: token}
        )

    async def _create_client(
        self,
        username: str,
        *,
        password: str | None = None,
        token: str | None = None,
    ):
        """Create client."""
        try:
            async with asyncio.timeout(10):
                if (acquired_token := token) is None:
                    acquired_token = await pymelcloud.login(
                        username,
                        password,
                        async_get_clientsession(self.hass),
                    )
                await pymelcloud.get_devices(
                    acquired_token,
                    async_get_clientsession(self.hass),
                )
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                await async_create_import_issue(
                    self.hass, self.context["source"], "invalid_auth"
                )
                return self.async_abort(reason="invalid_auth")
            await async_create_import_issue(
                self.hass, self.context["source"], "cannot_connect"
            )
            return self.async_abort(reason="cannot_connect")
        except (asyncio.TimeoutError, ClientError):
            await async_create_import_issue(
                self.hass, self.context["source"], "cannot_connect"
            )
            return self.async_abort(reason="cannot_connect")

        return await self._create_entry(username, acquired_token)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
                ),
            )
        username = user_input[CONF_USERNAME]
        return await self._create_client(username, password=user_input[CONF_PASSWORD])

    async def async_step_import(self, user_input):
        """Import a config entry."""
        result = await self._create_client(
            user_input[CONF_USERNAME], token=user_input[CONF_TOKEN]
        )
        if result["type"] == FlowResultType.CREATE_ENTRY:
            await async_create_import_issue(self.hass, self.context["source"], "", True)
        return result
