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

        try:
            await client.async_get_prices()
        except (EssentConnectionError, EssentResponseError):
            return self.async_abort(reason="cannot_connect")
        except EssentDataError:
            return self.async_abort(reason="invalid_data")
        except Exception:
            _LOGGER.exception("Unexpected error while validating the connection")
            return self.async_abort(reason="unknown")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title="Essent", data={})
