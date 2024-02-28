"""Config flow for Open Exchange Rates integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aioopenexchangerates import (
    Client,
    OpenExchangeRatesAuthError,
    OpenExchangeRatesClientError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_BASE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_TIMEOUT, DEFAULT_BASE, DOMAIN, LOGGER


def get_data_schema(
    currencies: dict[str, str], existing_data: Mapping[str, str]
) -> vol.Schema:
    """Return a form schema."""
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY): str,
            vol.Optional(
                CONF_BASE, default=existing_data.get(CONF_BASE) or DEFAULT_BASE
            ): vol.In(currencies),
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    client = Client(data[CONF_API_KEY], async_get_clientsession(hass))

    async with asyncio.timeout(CLIENT_TIMEOUT):
        await client.get_latest(base=data[CONF_BASE])

    return {"title": data[CONF_BASE]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Exchange Rates."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.currencies: dict[str, str] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        currencies = await self.async_get_currencies()

        if user_input is None:
            existing_data: Mapping[str, str] | dict[str, str] = (
                self._reauth_entry.data if self._reauth_entry else {}
            )
            return self.async_show_form(
                step_id="user",
                data_schema=get_data_schema(currencies, existing_data),
                description_placeholders={
                    "signup": "https://openexchangerates.org/signup"
                },
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except OpenExchangeRatesAuthError:
            errors["base"] = "invalid_auth"
        except OpenExchangeRatesClientError:
            errors["base"] = "cannot_connect"
        except TimeoutError:
            errors["base"] = "timeout_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._async_abort_entries_match(
                {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_BASE: user_input[CONF_BASE],
                }
            )

            if self._reauth_entry is not None:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=self._reauth_entry.data | user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=get_data_schema(currencies, user_input),
            description_placeholders={"signup": "https://openexchangerates.org/signup"},
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_get_currencies(self) -> dict[str, str]:
        """Get the available currencies."""
        if not self.currencies:
            client = Client("dummy-api-key", async_get_clientsession(self.hass))
            try:
                async with asyncio.timeout(CLIENT_TIMEOUT):
                    self.currencies = await client.get_currencies()
            except OpenExchangeRatesClientError as err:
                raise AbortFlow("cannot_connect") from err
            except TimeoutError as err:
                raise AbortFlow("timeout_connect") from err
        return self.currencies
