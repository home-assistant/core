"""Config flow for the SensorPush Cloud integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .api import SensorPushCloudApi, SensorPushCloudError
from .const import CONF_DEVICE_IDS, DOMAIN, LOGGER


class SensorPushCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SensorPush Cloud."""

    VERSION = 1

    api: SensorPushCloudApi | None
    data: dict[str, Any]

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data = {}

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration step."""
        if TYPE_CHECKING:
            assert self.api is not None
        if user_input is not None:
            if not user_input[CONF_DEVICE_IDS]:
                return self.async_abort(reason="no_devices_selected")
            self.data |= user_input
            return self.async_create_entry(title=self.data[CONF_EMAIL], data=self.data)

        errors: dict[str, str] = {}
        options: list[SelectOptionDict] = []
        try:
            sensors = await self.api.async_sensors()
            options = [{"value": k, "label": v["name"]} for k, v in sensors.items()]
        except SensorPushCloudError as e:
            errors["base"] = str(e)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if not options:
                errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_IDS, default=[]): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email, password = user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            self.api = SensorPushCloudApi(self.hass, email, password)
            await self.async_set_unique_id(email, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            try:
                await self.api.async_authorize()
            except SensorPushCloudError as e:
                errors["base"] = str(e)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.data |= user_input
                return await self.async_step_configure()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
