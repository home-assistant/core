"""Config flow for Browan integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from pyliblorawan.helpers.exceptions import (
    CannotConnect,
    DeviceEuiNotFound,
    InvalidAuth,
    InvalidDeviceEui,
)
from pyliblorawan.models import Device
from pyliblorawan.network_servers.ttn import TTN
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_RE_DEVICE_EUI = re.compile(r"^[0-9a-fA-F]{16}$")

_DEVICE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[SelectOptionDict(value="TBMS100", label="TBMS100")],
        mode=SelectSelectorMode.DROPDOWN,
    )
)

_STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="https://eu1.cloud.thethings.network"): str,
        vol.Required("application"): str,
        vol.Required("api_key"): str,
        vol.Required("device_eui"): str,
        vol.Required(CONF_MODEL): _DEVICE_SELECTOR,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> Device:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    ttn = TTN(data["api_key"], data["application"], data[CONF_URL])

    if not _RE_DEVICE_EUI.match(data["device_eui"]):
        raise InvalidDeviceEui(data["device_eui"])

    device_eui: str = data["device_eui"].upper()
    devices = await ttn.list_device_euis(session)

    if device_eui not in [device.device_eui for device in devices]:
        raise DeviceEuiNotFound(device_eui)

    # As device_eui is unique it will be 1 dimension max
    device = [device for device in devices if device.device_eui == device_eui][0]

    # Return info that you want to store in the config entry.
    return device


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Browan."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device = await validate_input(self.hass, user_input)
            except CannotConnect as e:
                errors["base"] = f"cannot_connect: {str(e)}"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except DeviceEuiNotFound as e:
                errors["base"] = f'Device "{str(e)}" is not in the application'
            except InvalidDeviceEui as e:
                errors[
                    "base"
                ] = f'Invalid device EUI "{str(e)}". It should match "^[0-9a-fA-F]{{16}}$"'
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device.device_eui)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=device.name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_STEP_USER_DATA_SCHEMA, errors=errors
        )
