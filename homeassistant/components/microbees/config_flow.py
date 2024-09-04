"""Config flow for microBees integration."""

from collections.abc import Mapping
import logging
from typing import Any

from microBeesPy import MicroBees, MicroBeesException

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for microBees."""

    DOMAIN = DOMAIN
    reauth_entry: config_entries.ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["read", "write"]
        return {"scope": " ".join(scopes)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""

        microbees = MicroBees(
            session=aiohttp_client.async_get_clientsession(self.hass),
            token=data[CONF_TOKEN][CONF_ACCESS_TOKEN],
        )

        try:
            current_user = await microbees.getMyProfile()
        except MicroBeesException:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            self.logger.exception("Unexpected error")
            return self.async_abort(reason="unknown")

        if not self.reauth_entry:
            await self.async_set_unique_id(current_user.id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=current_user.username,
                data=data,
            )
        if self.reauth_entry.unique_id == current_user.id:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
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
