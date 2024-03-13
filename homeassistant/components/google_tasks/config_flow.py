"""Config flow for Google Tasks."""
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Tasks OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow."""
        try:
            resource = build(
                "tasks",
                "v1",
                credentials=Credentials(token=data[CONF_TOKEN][CONF_ACCESS_TOKEN]),
            )
            cmd: HttpRequest = resource.tasklists().list()
            await self.hass.async_add_executor_job(cmd.execute)
        except HttpError as ex:
            error = ex.reason
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.exception("Unknown error occurred: %s", ex)
            return self.async_abort(reason="unknown")
        return self.async_create_entry(title=self.flow_impl.name, data=data)
