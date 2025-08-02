"""Config flow for Green Planet Energy integration."""

from __future__ import annotations

import asyncio
from datetime import date
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    api_url = "https://mein.green-planet-energy.de/p2"

    # Test API Verbindung
    today = date.today()
    payload = {
        "jsonrpc": "2.0",
        "method": "getVerbrauchspreisUndWindsignal",
        "params": {
            "von": today.strftime("%Y-%m-%d"),
            "bis": today.strftime("%Y-%m-%d"),
            "aggregatsZeitraum": "",
            "aggregatsTyp": "",
            "source": "Portal"
        },
        "id": 564
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://mein.green-planet-energy.de/dynamischer-tarif/strompreise"
    }

    def _check_response_status(response_status: int) -> None:
        """Check API response status."""
        if response_status != 200:
            raise ValueError(f"API returned status {response_status}")

    try:
        async with asyncio.timeout(10):
            async with session.post(api_url, json=payload, headers=headers) as response:
                _check_response_status(response.status)

                # API gibt text/html zurück, aber enthält trotzdem JSON
                await response.json(content_type=None)  # Teste ob JSON geparst werden kann

    except TimeoutError as err:
        raise ValueError("Timeout beim Verbinden zur Green Planet Energy API") from err
    except aiohttp.ClientError as err:
        raise ValueError(f"Verbindung zur Green Planet Energy API fehlgeschlagen: {err}") from err
    except Exception as err:
        raise ValueError(f"Unerwarteter Fehler bei API-Validierung: {err}") from err

    # Return info that you want to store in the config entry.
    return {"title": "Green Planet Energy"}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Green Planet Energy."""

    VERSION = 1
    MINOR_VERSION = 1

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
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
