"""Config Flow for Teslemetry integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientConnectionError
from tesla_fleet_api import Teslemetry
from tesla_fleet_api.exceptions import InvalidToken, PaymentRequired, TeslaFleetError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

TESLEMETRY_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})
DESCRIPTION_PLACEHOLDERS = {
    "short_url": "teslemetry.com/console",
    "url": "[teslemetry.com/console](https://teslemetry.com/console)",
}


class TeslemetryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Teslemetry API connection."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Get configuration from the user."""
        errors: dict[str, str] = {}
        if user_input:
            teslemetry = Teslemetry(
                session=async_get_clientsession(self.hass),
                access_token=user_input[CONF_ACCESS_TOKEN],
            )
            try:
                await teslemetry.test()
            except InvalidToken:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
            except PaymentRequired:
                errors["base"] = "subscription_required"
            except ClientConnectionError:
                errors["base"] = "cannot_connect"
            except TeslaFleetError as e:
                LOGGER.exception(str(e))
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Teslemetry",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=TESLEMETRY_SCHEMA,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )
