"""Config flow for Eufy RoboVac."""

from dataclasses import replace
from typing import Any, override

from eufy_robovac import (
    AuthenticationError,
    CloudClient,
    RoboVac,
    RoboVacConnectionError,
    RoboVacInfo,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_LOCAL_KEY, CONF_PROTOCOL_VERSION, DOMAIN

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class EufyRoboVacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Eufy RoboVac config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._devices: dict[str, RoboVacInfo] = {}
        self._selected_device: RoboVacInfo | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover supported vacuums using Eufy account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                devices = await CloudClient(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                ).list_devices()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RoboVacConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if devices:
                    self._devices = {device.device_id: device for device in devices}
                    return await self.async_step_select_device()
                errors["base"] = "no_devices"

        return self.async_show_form(
            step_id="user", data_schema=ACCOUNT_SCHEMA, errors=errors
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a discovered vacuum."""
        if user_input is not None:
            self._selected_device = self._devices[user_input[CONF_DEVICE_ID]]
            await self.async_set_unique_id(self._selected_device.device_id)
            self._abort_if_unique_id_configured()
            return await self.async_step_device()

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=device.device_id, label=device.name
                                )
                                for device in self._devices.values()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm local connection details and validate the vacuum."""
        assert self._selected_device is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            info = replace(
                self._selected_device,
                host=user_input[CONF_HOST],
                protocol_version=user_input[CONF_PROTOCOL_VERSION],
            )
            try:
                await RoboVac(info).update()
            except RoboVacConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=info.name,
                    data={
                        CONF_NAME: info.name,
                        CONF_MODEL: info.model,
                        CONF_DEVICE_ID: info.device_id,
                        CONF_LOCAL_KEY: info.local_key,
                        CONF_HOST: info.host,
                        CONF_PROTOCOL_VERSION: info.protocol_version,
                    },
                )

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(
                            user_input[CONF_HOST]
                            if user_input is not None
                            else self._selected_device.host
                        ),
                    ): str,
                    vol.Required(
                        CONF_PROTOCOL_VERSION,
                        default=(
                            user_input[CONF_PROTOCOL_VERSION]
                            if user_input is not None
                            else self._selected_device.protocol_version
                        ),
                    ): str,
                }
            ),
            errors=errors,
        )
