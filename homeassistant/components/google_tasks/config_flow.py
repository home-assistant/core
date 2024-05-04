"""Config flow for Google Tasks."""

from collections.abc import Mapping
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Tasks OAuth2 authentication."""

    DOMAIN = DOMAIN

    reauth_entry: ConfigEntry | None = None

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

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        credentials = Credentials(token=data[CONF_TOKEN][CONF_ACCESS_TOKEN])
        try:
            user_resource = build(
                "oauth2",
                "v2",
                credentials=credentials,
            )
            user_resource_cmd: HttpRequest = user_resource.userinfo().get()
            user_resource_info = await self.hass.async_add_executor_job(
                user_resource_cmd.execute
            )
            resource = build(
                "tasks",
                "v1",
                credentials=credentials,
            )
            cmd: HttpRequest = resource.tasklists().list()
            await self.hass.async_add_executor_job(cmd.execute)
        except HttpError as ex:
            error = ex.reason
            return self.async_abort(
                reason="access_not_configured",
                description_placeholders={"message": error},
            )
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("Unknown error occurred")
            return self.async_abort(reason="unknown")
        user_id = user_resource_info["id"]
        if not self.reauth_entry:
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_resource_info["name"], data=data)

        if self.reauth_entry.unique_id == user_id or not self.reauth_entry.unique_id:
            return self.async_update_reload_and_abort(
                self.reauth_entry, unique_id=user_id, data=data
            )

        return self.async_abort(reason="wrong_account")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
