"""Config flow for Imou."""

import logging
from typing import Any, override

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

IMOU_DHCP_DISCOVERY = "imou_dhcp_discovery"


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via DHCP. MAC/IP are not stored."""
        if self.hass.config_entries.async_has_entries(DOMAIN):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(IMOU_DHCP_DISCOVERY)
        self._abort_if_unique_id_configured()
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm cloud setup after a DHCP match."""
        if user_input is not None:
            return await self.async_step_user()

        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm")

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_APP_ID])
            self._abort_if_unique_id_configured()
            api_client = ImouOpenApiClient(
                user_input[CONF_APP_ID],
                user_input[CONF_APP_SECRET],
                API_URLS[user_input[CONF_API_URL]],
            )
            try:
                await api_client.async_get_token()
            except InvalidAppIdOrSecretException:
                errors["base"] = "invalid_auth"
            except ConnectFailedException, RequestFailedException:
                errors["base"] = "cannot_connect"
            except ImouException as exception:
                _LOGGER.debug("Imou error during config flow: %s", exception)
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Imou",
                    data={
                        CONF_APP_ID: user_input[CONF_APP_ID],
                        CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        CONF_API_URL: user_input[CONF_API_URL],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_APP_SECRET): str,
                    vol.Required(CONF_API_URL, default="sg"): SelectSelector(
                        SelectSelectorConfig(
                            options=list(API_URLS),
                            translation_key="api_url",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
