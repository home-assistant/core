"""Config flow for zcc integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zcc import (
    ControlPoint,
    ControlPointDescription,
    ControlPointDiscoveryService,
    ControlPointError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DEFAULT_PORT, DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

SELECTED_HOST_AND_PORT = "selected_host_and_port"

# class ZimiConfigErrors(StrEnum):
#     """ZimiConfig errors."""

#     ALREADY_CONFIGURED = "already_configured"
#     CANNOT_CONNECT = "cannot_connect"
#     CONNECTION_REFUSED = "connection_refused"
#     DISCOVERY_FAILURE = "discovery_failure"
#     INVALID_HOST = "invalid_host"
#     INVALID_PORT = "invalid_port"
#     TIMEOUT = "timeout"
#     UNKNOWN = "unknown"


class ZimiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcc."""

    api: ControlPoint = None
    api_descriptions: list[ControlPointDescription]
    data: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial auto-discovery step."""

        self.data = {}

        try:
            self.api_descriptions = await ControlPointDiscoveryService().discovers()
        except ControlPointError:
            # ControlPointError is expected if no zcc are found on LAN
            return await self.async_step_manual()

        if len(self.api_descriptions) == 1:
            self.data[CONF_HOST] = self.api_descriptions[0].host
            self.data[CONF_PORT] = self.api_descriptions[0].port
            return await self.create_entry()

        return await self.async_step_selection()

    async def async_step_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selection of zcc to configure if multiple are discovered."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.data[CONF_HOST] = user_input[SELECTED_HOST_AND_PORT].split(":")[0]
            self.data[CONF_PORT] = int(user_input[SELECTED_HOST_AND_PORT].split(":")[1])

            connection_errors = await self.check_connection(
                self.data[CONF_HOST], self.data[CONF_PORT]
            )

            if not connection_errors:
                return await self.create_entry()

            errors = connection_errors

        available_options = [
            SelectOptionDict(
                label=f"{description.host}:{description.port}",
                value=f"{description.host}:{description.port}",
            )
            for description in self.api_descriptions
        ]

        available_schema = vol.Schema(
            {
                vol.Required(
                    SELECTED_HOST_AND_PORT, default=available_options[0]["value"]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=available_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="selection", data_schema=available_schema, errors=errors
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration step if needed."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self.data = {**self.data, **user_input}

            connection_errors = await self.check_connection(
                self.data[CONF_HOST], self.data[CONF_PORT]
            )

            if not connection_errors:
                return await self.create_entry()

            errors = connection_errors

        return self.async_show_form(
            step_id="manual",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, self.data
            ),
            errors=errors,
        )

    async def check_connection(self, host: str, port: int) -> None | dict[str, str]:
        """Check connection to zcc.

        Stores mac and returns None if successful, otherwise returns error message.
        """

        result = await ControlPointDiscoveryService().validate_connection(
            self.data[CONF_HOST], self.data[CONF_PORT]
        )

        if details := result.get("result"):
            self.data[CONF_MAC] = format_mac(details.mac)
            return None

        return {"base": result["errors"]}

    async def create_entry(self) -> ConfigFlowResult:
        """Create entry for zcc."""

        await self.async_set_unique_id(self.data[CONF_MAC])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{TITLE} ({self.data[CONF_HOST]}:{self.data[CONF_PORT]})",
            data=self.data,
        )
