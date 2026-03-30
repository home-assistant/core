"""Config flow for Rainforest Eagle integration."""

from __future__ import annotations

import logging
from typing import Any

from aioeagle import ElectricMeter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TYPE

from .const import CONF_CLOUD_ID, CONF_HARDWARE_ADDRESS, CONF_INSTALL_CODE, DOMAIN
from .data import CannotConnect, InvalidAuth, async_get_type

_LOGGER = logging.getLogger(__name__)


def create_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Create user schema with passed in defaults if available."""
    if user_input is None:
        user_input = {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
            vol.Required(CONF_CLOUD_ID, default=user_input.get(CONF_CLOUD_ID)): str,
            vol.Required(
                CONF_INSTALL_CODE, default=user_input.get(CONF_INSTALL_CODE)
            ): str,
        }
    )


class RainforestEagleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rainforest Eagle."""

    VERSION = 1
    _meters: list[ElectricMeter] | None = None
    _user_input: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=create_schema(user_input)
            )

        await self.async_set_unique_id(user_input[CONF_CLOUD_ID])
        errors = {}

        try:
            eagle_type, meters = await async_get_type(
                self.hass,
                user_input[CONF_CLOUD_ID],
                user_input[CONF_INSTALL_CODE],
                user_input[CONF_HOST],
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            user_input[CONF_TYPE] = eagle_type

            if meters:
                # If there are meters, the process depends on how many there are and if any have a 'Connected' status
                if len(meters) == 1:
                    # If there is only one meter, just use it and create the entry
                    user_input[CONF_HARDWARE_ADDRESS] = meters[0].hardware_address
                else:
                    # If there are multiple meters, look for the first one with a 'Connected' status
                    selected_meter = None
                    for meter in meters:
                        if getattr(meter, "connection_status", None) == "Connected":
                            selected_meter = meter
                            break

                    if selected_meter:
                        # If a connected meter was found, use that and create the entry
                        user_input[CONF_HARDWARE_ADDRESS] = (
                            selected_meter.hardware_address
                        )

                    else:
                        # If there was more than one meter, but none have a 'Connected' status, then let the user choose
                        self._meters = meters
                        self._user_input = user_input
                        return await self.async_step_meter_select()
            else:
                # If there are no meters, set to None
                user_input[CONF_HARDWARE_ADDRESS] = None

            return self.async_create_entry(
                title=user_input[CONF_CLOUD_ID], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=create_schema(user_input), errors=errors
        )

    async def async_step_meter_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle meter selection step."""
        if user_input is None:
            # Create a list of meter choices
            assert self._meters is not None
            meter_choices = {
                meter.hardware_address: f"Meter #{i + 1}: ({meter.connection_status}) hardware address {meter.hardware_address}"
                for i, meter in enumerate(self._meters)
            }

            return self.async_show_form(
                step_id="meter_select",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HARDWARE_ADDRESS): vol.In(meter_choices),
                    }
                ),
                description_placeholders={"meter_count": str(len(self._meters))},
            )

        # Add the selected meter to the stored user input
        assert self._user_input is not None
        self._user_input[CONF_HARDWARE_ADDRESS] = user_input[CONF_HARDWARE_ADDRESS]
        return self.async_create_entry(
            title=self._user_input[CONF_CLOUD_ID], data=self._user_input
        )
