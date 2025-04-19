"""Config flow for Miele."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

UNIQUE_ID = "miele"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Miele OAuth2 authentication."""

    DOMAIN = DOMAIN
    name: str = ""

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        # "vg" is mandatory but the value doesn't seem to matter
        return {
            "vg": "sv-SE",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )

        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated reconfiguration."""
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create or update the config entry."""

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        return await super().async_oauth_create_entry(data)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a zeroconf discovered Miele device."""
        self.name = discovery_info.name.split(".", 1)[0]
        # The unique_id here is needed for zeroconf discovery to behave properly
        await self.async_set_unique_id(unique_id=UNIQUE_ID)
        self._abort_if_unique_id_configured()

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""

        if user_input is not None:
            return await self.async_step_user()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={CONF_NAME: self.name},
        )
