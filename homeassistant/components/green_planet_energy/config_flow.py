"""Config flow for Green Planet Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from greenplanet_energy_api import (
    GreenPlanetEnergyAPI,
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GreenPlanetEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Green Planet Energy."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = GreenPlanetEnergyAPI(session=session)
            try:
                await api.get_electricity_prices()
            except GreenPlanetEnergyConnectionError:
                errors["base"] = "cannot_connect"
            except GreenPlanetEnergyAPIError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Green Planet Energy", data=user_input
                )

        return self.async_show_form(step_id="user", errors=errors)
