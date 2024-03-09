"""Config flow to configure the RDW integration."""

from __future__ import annotations

from typing import Any

from vehicle import RDW, RDWError, RDWUnknownLicensePlateError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LICENSE_PLATE, DOMAIN


class RDWFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for RDW."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            rdw = RDW(session=session)
            try:
                vehicle = await rdw.vehicle(
                    license_plate=user_input[CONF_LICENSE_PLATE]
                )
            except RDWUnknownLicensePlateError:
                errors["base"] = "unknown_license_plate"
            except RDWError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(vehicle.license_plate)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_LICENSE_PLATE],
                    data={
                        CONF_LICENSE_PLATE: vehicle.license_plate,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LICENSE_PLATE): str,
                }
            ),
            errors=errors,
        )
