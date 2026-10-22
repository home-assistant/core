"""Config flow for Google Docs."""

from collections.abc import Mapping
import logging
from typing import Any, override

import gdocs_client

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_ACCESS, DEFAULT_DOCUMENT_NAME, DEFAULT_NAME, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle Google Docs OAuth authorization."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the integration logger."""
        return logging.getLogger(__name__)

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Request limited file access and a refresh token, as Google Sheets does."""
        return {
            "scope": DEFAULT_ACCESS,
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication of the existing document entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to authorize the account again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create one document, or reconnect the existing one after reauth."""
        if DEFAULT_ACCESS not in data[CONF_TOKEN].get("scope", "").split():
            return self.async_abort(reason="missing_scope")

        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            assert entry.unique_id is not None
            try:
                await self.hass.async_add_executor_job(
                    gdocs_client.get_document, access_token, entry.unique_id, False
                )
            except gdocs_client.API_ERRORS:
                return self.async_abort(reason="open_document_failure")
            return self.async_update_reload_and_abort(entry, data=data)

        try:
            document = await self.hass.async_add_executor_job(
                gdocs_client.create_document, access_token, DEFAULT_DOCUMENT_NAME
            )
        except gdocs_client.API_ERRORS:
            return self.async_abort(reason="create_document_failure")

        await self.async_set_unique_id(document["documentId"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DEFAULT_NAME,
            data=data,
            description_placeholders={
                "url": f"https://docs.google.com/document/d/{document['documentId']}/edit"
            },
        )
