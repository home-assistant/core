"""Config flow for Tesla Powerwall integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _test_connection(ip_address: str, password: str) -> dict[str, str]:
    """Test connection to powerwall and return info."""
    import pypowerwall  # noqa: PLC0415

    try:
        pw = pypowerwall.Powerwall(
            host=ip_address,
            password=password,
            email="homeassistant@local",
            timezone="UTC",
        )
    except Exception as err:
        _LOGGER.error("Failed to create Powerwall instance: %s", err)
        raise CannotConnect from err

    # Test connection by getting battery level
    try:
        level = pw.level()
    except Exception as err:
        _LOGGER.error("Failed to get battery level: %s", err)
        raise CannotConnect from err

    if level is None:
        raise CannotConnect("Unable to connect to Powerwall")

    # Get site name if available (PW2), else use IP
    site_name = pw.site_name()
    title = site_name or f"Powerwall 3 ({ip_address})"

    return {"title": title, "unique_id": ip_address}


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    ip_address = data[CONF_IP_ADDRESS]
    password = data.get(CONF_PASSWORD, "")

    try:
        return await hass.async_add_executor_job(_test_connection, ip_address, password)
    except Exception as err:
        _LOGGER.error("Connection test failed: %s", err)
        raise CannotConnect from err


class PowerwallConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the powerwall flow."""
        self.ip_address: str | None = None
        self.title: str | None = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery.

        Retained for backwards compatibility with Powerwall 2 gateways
        which broadcast DHCP hostnames matching 1118431-* / 1232100-*.
        Powerwall 3 does not broadcast a DHCP hostname, so discovery
        will not trigger for PW3 — users must add PW3 manually.
        """
        self.ip_address = discovery_info.ip

        # Use gateway hostname as stable unique_id instead of IP
        gateway_id = discovery_info.hostname
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured(updates={CONF_IP_ADDRESS: self.ip_address})
        self.context["title_placeholders"] = {CONF_IP_ADDRESS: self.ip_address}
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured(
                    updates={CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]}
                )
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS, default=self.ip_address): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.ip_address = entry_data[CONF_IP_ADDRESS]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    {CONF_IP_ADDRESS: reauth_entry.data[CONF_IP_ADDRESS], **user_input},
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): str}),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
