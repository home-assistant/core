"""Config flow for ViCare integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

# from PyViCare.PyViCareUtils import (
#     PyViCareInvalidConfigurationError,
#     PyViCareInvalidCredentialsError,
# )
import voluptuous as vol

# from homeassistant.components import dhcp
from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlowResult

# from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.device_registry import format_mac

from .const import CONF_HEATING_TYPE, DEFAULT_HEATING_TYPE, DOMAIN, HeatingType

_LOGGER = logging.getLogger(__name__)

SCOPES = [
    "IoT User",
    "offline_access",  # required to get a refresh_token
]

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE.value): vol.In(
            [e.value for e in HeatingType]
        ),
    }
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Viessmann ViCare OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 2

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SCOPES),
        }

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Invoke when a Viessmann MAC address is discovered on the network."""
        formatted_mac = format_mac(discovery_info.macaddress)
        _LOGGER.debug("Found device with mac %s", formatted_mac)

        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        #     errors: dict[str, str] = {}

        #     if user_input is not None:
        #         try:
        #             await self.hass.async_add_executor_job(
        #                 vicare_login, user_input
        #             )
        #         except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError):
        #             errors["base"] = "invalid_auth"
        #         else:
        #             return self.async_create_entry(title=VICARE_NAME, data=user_input)

        #     return self.async_show_form(
        #         step_id="user",
        #         data_schema=USER_SCHEMA,
        #         errors=errors,
        #     )

        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={CONF_NAME: self._get_reauth_entry().title},
            )

        return await self.async_step_user()
