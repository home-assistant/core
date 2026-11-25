"""Config flow for Ecoforest integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from httpx2 import BasicAuth
import probatio
from pyecoforest.api import EcoforestApi
from pyecoforest.exceptions import (
    EcoforestAuthenticationRequired,
    EcoforestConnectionError,
)
from pyecoforest.models.device import Device

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


async def _async_get_device(
    host: str, username: str, password: str, errors: dict[str, str]
) -> Device | None:
    """Return the device, or set an error in errors when it fails."""
    try:
        return await EcoforestApi(host, BasicAuth(username, password)).get()
    except EcoforestAuthenticationRequired:
        errors["base"] = "invalid_auth"
    except EcoforestConnectionError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
    return None


class EcoForestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecoforest."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = await _async_get_device(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                errors,
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{MANUFACTURER} {device.serial_number}", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        suggested_values: Mapping[str, Any] = reauth_entry.data

        if user_input is not None:
            suggested_values = user_input
            device = await _async_get_device(
                reauth_entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                errors,
            )
            if device is not None:
                await self.async_set_unique_id(device.serial_number)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                {CONF_USERNAME: suggested_values[CONF_USERNAME]},
            ),
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            errors=errors,
        )
