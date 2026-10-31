"""Config flow for Google Docs."""

import logging
from typing import Any, override

import gdocs_client

from homeassistant.config_entries import ConfigFlowResult
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

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create one document after authorization."""
        if DEFAULT_ACCESS not in data[CONF_TOKEN].get("scope", "").split():
            return self.async_abort(reason="missing_scope")

        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
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
