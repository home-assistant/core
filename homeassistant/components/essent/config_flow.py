"""Config flow for Essent integration."""

from __future__ import annotations

import logging
from typing import Any

from essent_dynamic_pricing import (
    EssentClient,
    EssentConnectionError,
    EssentDataError,
    EssentResponseError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EssentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Essent."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        client = EssentClient(async_get_clientsession(self.hass))
        errors: dict[str, str] = {}

        try:
            await client.async_get_prices()
        except (EssentConnectionError, EssentResponseError):
            errors["base"] = "cannot_connect"
        except EssentDataError as err:
            _LOGGER.warning("Received invalid data while validating Essent: %s", err)
            errors["base"] = "invalid_data"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while validating the connection")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="user", errors=errors)

        return self.async_create_entry(title="Essent", data={})
