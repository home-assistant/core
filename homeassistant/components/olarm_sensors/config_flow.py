"""Module used for a GUI to configure the device."""
import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    AUTHENTICATION_ERROR,
    CONF_ALARM_CODE,
    CONF_DEVICE_FIRMWARE,
    CONF_OLARM_DEVICES,
    DOMAIN,
    LOGGER,
    OLARM_DEVICE_AMOUNT,
    OLARM_DEVICE_NAMES,
    OLARM_DEVICES,
)
from .coordinator import OlarmCoordinator
from .exceptions import APIForbiddenError
from .olarm_api import OlarmSetupApi


class OlarmSensorsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Olarm Sensors."""

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors: dict = {str: Any}

        if user_input is None:
            return await self._show_setup_form()

        # If user_input is not None, the user has submitted the form
        if user_input is not None:
            # Validate the user input
            if not user_input[CONF_API_KEY]:
                errors[CONF_API_KEY] = "API key is required."

            if not user_input[CONF_SCAN_INTERVAL]:
                errors[CONF_SCAN_INTERVAL] = "Scan interval is required."

            elif user_input[CONF_SCAN_INTERVAL] < 5:
                errors[CONF_SCAN_INTERVAL] = "Scan interval must be at least 5 seconds."

            api_key = user_input[CONF_API_KEY]
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            if user_input[CONF_ALARM_CODE] == "1234567890":
                alarm_code = None

            else:
                alarm_code = user_input[CONF_ALARM_CODE]

            try:
                api = OlarmSetupApi(api_key)
                json = await api.get_olarm_devices()

            except APIForbiddenError:
                LOGGER.warning(
                    "User entered invalid credentials or API access is not enabled!"
                )
                errors[AUTHENTICATION_ERROR] = "Invalid credentials!"

            if json is None:
                errors[AUTHENTICATION_ERROR] = "Invalid credentials!"

            # If there are errors, show the setup form with error messages
            if errors:
                return await self._show_setup_form(errors=errors)

            setup_devices = [dev["deviceName"] for dev in json]

            # If there are no errors, create a config entry and return
            firmware = json[0]["deviceFirmware"]
            temp_entry = ConfigEntry(
                domain=DOMAIN,
                source="User",
                version=1,
                title="Olarm Sensors",
                data={
                    CONF_API_KEY: api_key,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_DEVICE_FIRMWARE: firmware,
                    CONF_ALARM_CODE: alarm_code,
                    CONF_OLARM_DEVICES: setup_devices,
                    OLARM_DEVICES: json,
                    OLARM_DEVICE_AMOUNT: len(json),
                    OLARM_DEVICE_NAMES: setup_devices,
                },
            )

            for device in json:
                if device["deviceName"] not in setup_devices:
                    continue

                await asyncio.sleep(2)
                coordinator = OlarmCoordinator(
                    self.hass,
                    entry=temp_entry,
                    device_id=device["deviceId"],
                    device_name=device["deviceName"],
                    device_make=device["deviceAlarmType"],
                )

                await coordinator.update_data()

                self.hass.data[DOMAIN][device["deviceId"]] = coordinator

            # Saving the device
            return self.async_create_entry(
                title="Olarm Sensors",
                data={
                    CONF_API_KEY: api_key,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_DEVICE_FIRMWARE: firmware,
                    CONF_ALARM_CODE: alarm_code,
                    CONF_OLARM_DEVICES: setup_devices,
                    OLARM_DEVICES: json,
                    OLARM_DEVICE_AMOUNT: len(json),
                    OLARM_DEVICE_NAMES: setup_devices,
                },
            )

        return self.async_show_form(step_id="user", data_schema=self._get_schema())

    def _get_schema(self):
        """Return the data schema for the user form."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY,
                    msg="The api key for your account.",
                    description={
                        "suggested_value": "Your Olarm API key",
                        "description": "API key for accessing the Olarm API. You can find your API key here: https://user.olarm.co/#/api",
                    },
                ): cv.string,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    msg="The update interval in seconds.",
                    description={
                        "suggested_value": 10,
                        "description": "Interval, in seconds, at which to scan the Olarm device for sensor data. Minimum value is 5 seconds.",
                    },
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Optional(
                    CONF_ALARM_CODE,
                    msg="The code for alarm actions. Leave default for no code.",
                    description={
                        "suggested_value": "1234567890",
                        "description": "Alarm Panel Code",
                    },
                ): cv.string,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OlarmOptionsFlow(config_entry)


class OlarmOptionsFlow(OptionsFlow):
    """Options for Olarm config."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    def _get_schema(self):
        """Return the data schema for the user form."""
        if self.config_entry.data[CONF_ALARM_CODE] is None:
            alarm_code = "1234567890"

        else:
            alarm_code = self.config_entry.data[CONF_ALARM_CODE]

        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY,
                    msg="The api key for your account.",
                    description={
                        "suggested_value": self.config_entry.data[CONF_API_KEY],
                        "description": "API key for accessing the Olarm API. You can find your API key here: https://user.olarm.co/#/api",
                    },
                ): cv.string,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    msg="The update interval in seconds.",
                    description={
                        "suggested_value": self.config_entry.data[CONF_SCAN_INTERVAL],
                        "description": "Interval, in seconds, at which to scan the Olarm device for sensor data. Minimum value is 5 seconds.",
                    },
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Optional(
                    CONF_ALARM_CODE,
                    msg="The code for alarm actions. Leave default for no code.",
                    description={
                        "suggested_value": alarm_code,
                        "description": "Alarm Panel Code",
                    },
                ): cv.string,
                vol.Optional(
                    CONF_OLARM_DEVICES,
                    msg="The Olarm devices to load into this Home Assistant instance.",
                    description={
                        "description": "The Olarm devices to load into this Home Assistant instance.",
                    },
                ): cv.multi_select(self.config_entry.data[OLARM_DEVICE_NAMES]),
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input[CONF_ALARM_CODE] == "1234567890":
                alarm_code = None

            else:
                alarm_code = user_input[CONF_ALARM_CODE]

            new = {**self.config_entry.data}

            new[CONF_ALARM_CODE] = alarm_code
            new[OLARM_DEVICE_AMOUNT] = len(self.config_entry.data[OLARM_DEVICE_NAMES])
            new[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            new[CONF_API_KEY] = user_input[CONF_API_KEY]
            new[CONF_OLARM_DEVICES] = user_input[CONF_OLARM_DEVICES]

            return self.async_create_entry(title="Olarm Sensors", data=new)

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_schema(),
        )
