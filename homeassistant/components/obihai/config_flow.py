"""Config flow to configure the Obihai integration."""

from __future__ import annotations

from socket import gaierror, gethostbyname
from typing import Any

from pyobihai import PyObihai
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .connectivity import validate_auth
from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(
            CONF_USERNAME,
            default=DEFAULT_USERNAME,
        ): str,
        vol.Required(
            CONF_PASSWORD,
            default=DEFAULT_PASSWORD,
        ): str,
    }
)


async def async_validate_creds(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> PyObihai | None:
    """Manage Obihai options."""

    return await hass.async_add_executor_job(
        validate_auth,
        user_input[CONF_HOST],
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
    )


class ObihaiFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Obihai."""

    VERSION = 2
    discovery_schema: vol.Schema | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        ip: str | None = None

        if user_input is not None:
            try:
                ip = gethostbyname(user_input[CONF_HOST])
            except gaierror:
                errors["base"] = "cannot_connect"

            if ip:
                if pyobihai := await async_validate_creds(self.hass, user_input):
                    device_mac = await self.hass.async_add_executor_job(
                        pyobihai.get_device_mac
                    )
                    await self.async_set_unique_id(device_mac)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_HOST],
                        data=user_input,
                    )
                errors["base"] = "invalid_auth"

        data_schema = self.discovery_schema or self.add_suggested_values_to_schema(
            DATA_SCHEMA, user_input
        )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=data_schema,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Prepare configuration for a DHCP discovered Obihai."""

        return await self.async_step_dhcp_confirm(discovery_info)

    async def async_step_dhcp_confirm(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> FlowResult:
        """Attempt to confirm."""

        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured()

        user_input = {
            CONF_HOST: discovery_info.ip,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_USERNAME: DEFAULT_USERNAME,
        }

        if await async_validate_creds(self.hass, user_input):
            self.discovery_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input
            )
        else:
            self.discovery_schema = self.add_suggested_values_to_schema(
                DATA_SCHEMA,
                {CONF_HOST: discovery_info.ip, CONF_USERNAME: "", CONF_PASSWORD: ""},
            )

        return await self.async_step_user()

    # DEPRECATED
    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Handle a flow initialized by importing a config."""

        try:
            _ = gethostbyname(config[CONF_HOST])
        except gaierror:
            return self.async_abort(reason="cannot_connect")

        if pyobihai := await async_validate_creds(self.hass, config):
            device_mac = await self.hass.async_add_executor_job(pyobihai.get_device_mac)
            await self.async_set_unique_id(device_mac)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=config.get(CONF_NAME, config[CONF_HOST]),
                data={
                    CONF_HOST: config[CONF_HOST],
                    CONF_PASSWORD: config[CONF_PASSWORD],
                    CONF_USERNAME: config[CONF_USERNAME],
                },
            )

        return self.async_abort(reason="invalid_auth")
