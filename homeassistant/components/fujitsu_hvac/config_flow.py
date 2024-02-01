"""Config flow for Fujitsu HVAC (based on Ayla IOT) integration."""
from asyncio import timeout
import logging
from typing import Any

from ayla_iot_unofficial import AylaAuthError, new_ayla_api
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    API_TIMEOUT,
    AYLA_APP_ID,
    AYLA_APP_SECRET,
    CONF_DEVICE,
    CONF_EUROPE,
    DOMAIN,
    NO_DEVICES_ERROR,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_EUROPE): bool,
    }
)


async def get_devices(data: dict[str, Any]) -> dict[str, Any]:
    """Get the list of devices from the ayla API."""
    api = new_ayla_api(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        AYLA_APP_ID,
        AYLA_APP_SECRET,
        europe=data[CONF_EUROPE],
    )
    try:
        async with timeout(API_TIMEOUT):
            await api.async_sign_in()
    except AylaAuthError as e:
        raise InvalidAuth from e
    except TimeoutError as e:
        raise CannotConnect from e

    devices = [
        device
        for device in await api.async_get_devices()
        if isinstance(device, FujitsuHVAC)
    ]
    for dev in devices:
        await dev.async_update()

    return {device.device_serial_number: device for device in devices}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu HVAC (based on Ayla IOT)."""

    VERSION = 1

    def __init__(self) -> None:
        """Create empty data."""
        self.devices: dict[str, FujitsuHVAC] = {}
        self.credentials: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.devices = await get_devices(user_input)
                self.credentials = user_input
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if len(self.devices) == 0:
                    return self.async_abort(reason=NO_DEVICES_ERROR)

                return self.async_show_form(
                    step_id="choose_device",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_DEVICE): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=[
                                        selector.SelectOptionDict(
                                            label=device.device_name,
                                            value=serial_number,
                                        )
                                        for (
                                            serial_number,
                                            device,
                                        ) in self.devices.items()
                                    ]
                                )
                            )
                        }
                    ),
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_choose_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to choose which device to configure."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE])
            self._abort_if_unique_id_configured()

            saved_data = user_input
            saved_data.update(self.credentials)

            return self.async_create_entry(
                title=self.devices[user_input[CONF_DEVICE]].device_name, data=saved_data
            )

        return self.async_abort(reason="Can't proceed without data")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
