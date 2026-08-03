"""Config flow for the WATERCryst integration."""

import logging
from typing import Any, override

from httpx import HTTPStatusError, RequestError
from pyocat import (
    AsyncApiClient,
    AsyncAuth,
    WTCApiDisabledError,
    WTCApiTemporaryError,
    WTCApiUnauthorizedError,
)
from pyocat.models import DeviceResponse
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_BSN, DOMAIN

_LOGGER = logging.getLogger(__name__)

_STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BSN): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> DeviceResponse:
    """Validate that the credentials work against the target device."""

    biocat_serial_number: str = data[CONF_BSN]
    key: str = data[CONF_API_KEY]

    auth = AsyncAuth(client=get_async_client(hass), api_key=key)
    client = AsyncApiClient(auth=auth)

    try:
        info = await client.get_device_info()

        if info.biocat_serial != biocat_serial_number:
            raise WrongDeviceSerial
    except WTCApiUnauthorizedError as err:
        raise InvalidAuth from err
    except WTCApiDisabledError as err:
        raise ApiDisabled from err
    return info


class WatercrystConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WATERCryst devices."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        The user enters the BIOCAT serial number and the API key.
        """

        errors: dict[str, str] = {}

        if user_input:
            try:
                info = await validate_input(self.hass, user_input)
            except ApiDisabled:
                errors["base"] = "api_disabled"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except WrongDeviceSerial:
                errors["base"] = "wrong_device_serial"
            except WTCApiTemporaryError:
                errors["base"] = "cannot_connect"
            except HTTPStatusError:
                errors["base"] = "cannot_connect"
            except RequestError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_BSN])
                self._abort_if_unique_id_configured()

                title = info.name or user_input[CONF_BSN]
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=_STEP_USER_DATA_SCHEMA, errors=errors
        )


class ApiDisabled(HomeAssistantError):
    """Error to indicate a disabled API endpoint."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class WrongDeviceSerial(HomeAssistantError):
    """Error to indicate that the entered BIOCAT serial is incorrect."""
