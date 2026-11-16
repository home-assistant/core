"""Config flow for Karaca Connect."""

from typing import Any, override

from karaca_connect_client import KaracaAuthError, KaracaClient, KaracaError
import probatio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_DEVICE_ID, DOMAIN


class KaracaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create entries for selected Karaca devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize account and device selection state."""
        self._email = ""
        self._password = ""
        self._devices: list[dict[str, Any]] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for Karaca account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            client = KaracaClient(
                async_get_clientsession(self.hass),
                email=self._email,
                password=self._password,
            )
            try:
                await client.login()
                devices = await client.get_devices()
                self._devices = [
                    device for device in devices if device.get("id") is not None
                ]
            except KaracaAuthError:
                errors["base"] = "invalid_auth"
            except KaracaError:
                errors["base"] = "cannot_connect"
            else:
                if not self._devices:
                    errors["base"] = "no_devices"
                elif len(self._devices) == 1:
                    return await self._create_entry_for_device(self._devices[0])
                else:
                    return await self.async_step_select_device()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_EMAIL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a device when multiple devices are present."""
        errors: dict[str, str] = {}
        choices = {
            str(device["id"]): str(
                device.get("label") or f"Karaca device {device['id']}"
            )
            for device in self._devices
            if device.get("id") is not None
        }
        if user_input is not None:
            device_id = str(user_input[CONF_DEVICE_ID])
            device = next(
                (d for d in self._devices if str(d.get("id")) == device_id),
                None,
            )
            if device is not None:
                return await self._create_entry_for_device(device)
            errors["base"] = "device_not_found"
        return self.async_show_form(
            step_id="select_device",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_DEVICE_ID): probatio.In(choices)}
            ),
            errors=errors,
        )

    async def _create_entry_for_device(
        self, device: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create a unique config entry for the device."""
        device_id = str(device["id"])
        await self.async_set_unique_id(f"karaca_{device_id}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=str(device.get("label") or "Karaca device"),
            data={
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_DEVICE_ID: device_id,
            },
        )
