"""Config flow for Gogogate2."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from ismartgate.common import AbstractInfoResponse, ApiError
from ismartgate.const import GogoGate2ApiErrorCode, ISmartGateApiErrorCode
import voluptuous as vol

from homeassistant.components import dhcp, zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import AbortFlow

from .common import get_api
from .const import DEVICE_TYPE_GOGOGATE2, DEVICE_TYPE_ISMARTGATE, DOMAIN

DEVICE_NAMES = {
    DEVICE_TYPE_GOGOGATE2: "Gogogate2",
    DEVICE_TYPE_ISMARTGATE: "ismartgate",
}


class Gogogate2FlowHandler(ConfigFlow, domain=DOMAIN):
    """Gogogate2 config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._ip_address: str | None = None
        self._device_type: str | None = None

    async def async_step_homekit(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle homekit discovery."""
        await self.async_set_unique_id(
            discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID]
        )
        return await self._async_discovery_handler(discovery_info.host)

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        await self.async_set_unique_id(discovery_info.macaddress)
        return await self._async_discovery_handler(discovery_info.ip)

    async def _async_discovery_handler(self, ip_address: str) -> ConfigFlowResult:
        """Start the user flow from any discovery."""
        self.context[CONF_IP_ADDRESS] = ip_address
        self._abort_if_unique_id_configured({CONF_IP_ADDRESS: ip_address})

        self._async_abort_entries_match({CONF_IP_ADDRESS: ip_address})

        self._ip_address = ip_address
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_IP_ADDRESS) == self._ip_address:
                raise AbortFlow("already_in_progress")

        self._device_type = DEVICE_TYPE_ISMARTGATE
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        user_input = user_input or {}
        errors = {}

        if user_input:
            api = get_api(self.hass, user_input)
            try:
                data: AbstractInfoResponse = await api.async_info()
                data_dict = dataclasses.asdict(data)
                title = data_dict.get(
                    "gogogatename", data_dict.get("ismartgatename", "Cover")
                )
                await self.async_set_unique_id(re.sub("\\..*$", "", data.remoteaccess))
                return self.async_create_entry(title=title, data=user_input)

            except ApiError as api_error:
                device_type = user_input[CONF_DEVICE]
                is_invalid_auth = (
                    device_type == DEVICE_TYPE_GOGOGATE2
                    and api_error.code
                    in (
                        GogoGate2ApiErrorCode.CREDENTIALS_NOT_SET,
                        GogoGate2ApiErrorCode.CREDENTIALS_INCORRECT,
                    )
                ) or (
                    device_type == DEVICE_TYPE_ISMARTGATE
                    and api_error.code
                    in (
                        ISmartGateApiErrorCode.CREDENTIALS_NOT_SET,
                        ISmartGateApiErrorCode.CREDENTIALS_INCORRECT,
                    )
                )

                if is_invalid_auth:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

        if self._ip_address and self._device_type:
            self.context["title_placeholders"] = {
                CONF_DEVICE: DEVICE_NAMES[self._device_type],
                CONF_IP_ADDRESS: self._ip_address,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE,
                        default=self._device_type
                        or user_input.get(CONF_DEVICE, DEVICE_TYPE_GOGOGATE2),
                    ): vol.In((DEVICE_TYPE_GOGOGATE2, DEVICE_TYPE_ISMARTGATE)),
                    vol.Required(
                        CONF_IP_ADDRESS,
                        default=user_input.get(CONF_IP_ADDRESS, self._ip_address),
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
        )
