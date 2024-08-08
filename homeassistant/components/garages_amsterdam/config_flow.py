"""Config flow for Garages Amsterdam integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
from odp_amsterdam import ODPAmsterdam, VehicleType
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GaragesAmsterdamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garages Amsterdam."""

    VERSION = 1
    _options: list[str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._options is None:
            self._options = []
            try:
                api_data = await ODPAmsterdam(
                    session=aiohttp_client.async_get_clientsession(self.hass)
                ).all_garages(vehicle=VehicleType.CAR)
            except ClientResponseError:
                _LOGGER.error("Unexpected response from server")
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

            for garage in sorted(api_data, key=lambda garage: garage.garage_name):
                self._options.append(garage.garage_name)

        if user_input is not None:
            await self.async_set_unique_id(user_input["garage_name"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input["garage_name"], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("garage_name"): vol.In(self._options)}
            ),
        )
