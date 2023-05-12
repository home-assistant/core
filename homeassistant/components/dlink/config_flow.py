"""Config flow for the D-Link Power Plug integration."""
from __future__ import annotations

import logging
from typing import Any

from pyW215.pyW215 import SmartPlug
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_USE_LEGACY_PROTOCOL, DEFAULT_NAME, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DLinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for D-Link Power Plug."""

    def __init__(self) -> None:
        """Initialize a D-Link Power Plug flow."""
        self.ip_address: str | None = None

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle dhcp discovery."""
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if not entry.unique_id and entry.data[CONF_HOST] == discovery_info.ip:
                # Add mac address as the unique id, can be removed with import
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=discovery_info.macaddress
                )
                return self.async_abort(reason="already_configured")

        self.ip_address = discovery_info.ip
        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""
        errors = {}
        if user_input is not None:
            if (
                error := await self.hass.async_add_executor_job(
                    self._try_connect, user_input
                )
            ) is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input | {CONF_HOST: self.ip_address},
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="confirm_discovery",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_USE_LEGACY_PROTOCOL): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            if (
                error := await self.hass.async_add_executor_job(
                    self._try_connect, user_input
                )
            ) is None:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )
            errors["base"] = error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=user_input.get(CONF_HOST, self.ip_address)
                    ): str,
                    vol.Optional(
                        CONF_USERNAME,
                        default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_USE_LEGACY_PROTOCOL): bool,
                }
            ),
            errors=errors,
        )

    def _try_connect(self, user_input: dict[str, Any]) -> str | None:
        """Try connecting to D-Link Power Plug."""
        try:
            smartplug = SmartPlug(
                user_input.get(CONF_HOST, self.ip_address),
                user_input[CONF_PASSWORD],
                user_input[CONF_USERNAME],
                user_input[CONF_USE_LEGACY_PROTOCOL],
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
            return "unknown"
        if not smartplug.authenticated and smartplug.use_legacy_protocol:
            return "cannot_connect"
        return None
