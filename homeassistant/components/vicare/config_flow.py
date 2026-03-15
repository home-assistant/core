"""Config flow for ViCare integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import (
    CONF_HEATING_TYPE,
    DEFAULT_HEATING_TYPE,
    DOMAIN,
    VICARE_NAME,
    HeatingType,
)

_LOGGER = logging.getLogger(__name__)


class ViCareFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for ViCare using OAuth2."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize ViCare flow handler."""
        super().__init__()
        self._heating_type: str = DEFAULT_HEATING_TYPE.value
        self._oauth_data: dict = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if self.source != SOURCE_REAUTH and self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await super().async_step_user(user_input)

    async def async_step_heating_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for their heating type after OAuth."""
        if user_input is not None:
            self._heating_type = user_input[CONF_HEATING_TYPE]
            return self.async_create_entry(
                title=VICARE_NAME,
                data={
                    **self._oauth_data,
                    CONF_HEATING_TYPE: self._heating_type,
                },
            )

        return self.async_show_form(
            step_id="heating_type",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE.value
                    ): vol.In([e.value for e in HeatingType]),
                }
            ),
        )

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry after OAuth or update existing for reauth."""
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={**reauth_entry.data, **data},
            )

        self._oauth_data = data
        return await self.async_step_heating_type()

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
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_user()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Invoke when a Viessmann MAC address is discovered on the network."""
        formatted_mac = format_mac(discovery_info.macaddress)
        _LOGGER.debug("Found device with mac %s", formatted_mac)

        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user()
