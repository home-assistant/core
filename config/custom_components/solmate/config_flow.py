"""Config flow for solmate integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("home_consumption"): EntitySelector(
            EntitySelectorConfig(device_class=SensorDeviceClass.POWER)
        ),
        vol.Required("pv_production"): EntitySelector(
            EntitySelectorConfig(device_class=SensorDeviceClass.POWER)
        ),
        vol.Required("home_battery_soc"): EntitySelector(
            EntitySelectorConfig(device_class=SensorDeviceClass.BATTERY)
        ),
        vol.Required("tesla_ble_device"): DeviceSelector(DeviceSelectorConfig()),
        vol.Required("fast_charge_button"): EntitySelector(
            EntitySelectorConfig(domain="binary_sensor")
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    return {"title": "Name of the device"}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for solmate."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle options flow for solmate integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=STEP_USER_DATA_SCHEMA,
        )
