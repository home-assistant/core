"""Config flow for Switcher integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from aioswitcher.device import DeviceType, SwitcherBase
from aioswitcher.device.tools import validate_token
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_KEY,
    CONF_DEVICE_TYPE,
    DOMAIN,
    PREREQUISITES_URL,
)
from .utils import async_discover_devices, async_test_device_connection

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_TOKEN): str,
    }
)

MANUAL_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_KEY): cv.string,
        vol.Required(CONF_DEVICE_TYPE): vol.In([dt.name for dt in DeviceType]),
    }
)


class SwitcherFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Switcher config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Init the config flow."""
        super().__init__()
        self.discovered_devices: dict[str, SwitcherBase] = {}
        self.username: str | None = None
        self.token: str | None = None
        self.manual_device_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discovery", "manual"],
        )

    async def async_step_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery-based setup."""
        self.discovered_devices = await async_discover_devices()

        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-confirmation of the config flow."""
        if len(self.discovered_devices) == 0:
            return self.async_abort(reason="no_devices_found")

        for device_id, device in self.discovered_devices.items():
            if device.token_needed:
                _LOGGER.debug("Device with ID %s requires a token", device_id)
                return await self.async_step_credentials()
        return await self._create_entry()

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.username = user_input.get(CONF_USERNAME)
            self.token = user_input.get(CONF_TOKEN)

            token_is_valid = await validate_token(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if token_is_valid:
                return await self._create_entry()
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="credentials",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
            description_placeholders={"prerequisites_url": PREREQUISITES_URL},
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token_is_valid = await validate_token(
                user_input[CONF_USERNAME], user_input[CONF_TOKEN]
            )
            if token_is_valid:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
            description_placeholders={"prerequisites_url": PREREQUISITES_URL},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual device configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Get the selected device type by name (e.g., "MINI")
                device_type_name = user_input[CONF_DEVICE_TYPE]
                device_type = DeviceType[device_type_name]

                response = await async_test_device_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_DEVICE_ID],
                    user_input[CONF_DEVICE_KEY],
                    device_type,
                )

                self.manual_device_data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_DEVICE_ID: user_input[CONF_DEVICE_ID],
                    CONF_DEVICE_KEY: user_input[CONF_DEVICE_KEY],
                    CONF_DEVICE_TYPE: device_type_name,
                }

                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()

                if getattr(response, "token_needed", False):
                    return await self.async_step_credentials()

                return await self._create_entry()

            except AbortFlow:
                raise
            except TimeoutError:
                _LOGGER.error("Network timeout connecting to device")
                errors["base"] = "cannot_connect"
            except ValueError:
                _LOGGER.error(
                    "Authentication failed - invalid credentials or device type"
                )
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during manual configuration")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="manual",
            data_schema=MANUAL_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_info": "Device ID and key can be found in the Switcher app settings"
            },
        )

    async def _create_entry(self) -> ConfigFlowResult:
        if self.manual_device_data:
            return self.async_create_entry(
                title="Switcher",
                data={
                    CONF_USERNAME: self.username,
                    CONF_TOKEN: self.token,
                    **self.manual_device_data,
                },
            )

        return self.async_create_entry(
            title="Switcher",
            data={
                CONF_USERNAME: self.username,
                CONF_TOKEN: self.token,
            },
        )
