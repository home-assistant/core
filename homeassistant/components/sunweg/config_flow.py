"""Config flow for Sun WEG integration."""

from collections.abc import Mapping
from typing import Any

from sunweg.api import APIHelper, SunWegApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import CONF_PLANT_ID, DOMAIN


class SunWEGConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise sun weg server flow."""
        self.api: APIHelper = None
        self.data: dict[str, Any] = {}

    @callback
    def _async_show_user_form(self, step_id: str, errors=None) -> ConfigFlowResult:
        """Show the form to the user."""
        default_username = ""
        if CONF_USERNAME in self.data:
            default_username = self.data[CONF_USERNAME]
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=default_username): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    def _set_auth_data(
        self, step: str, username: str, password: str
    ) -> ConfigFlowResult | None:
        """Set username and password."""
        if self.api:
            # Set username and password
            self.api.username = username
            self.api.password = password
        else:
            # Initialise the library with the username & password
            self.api = APIHelper(username, password)

        try:
            if not self.api.authenticate():
                return self._async_show_user_form(step, {"base": "invalid_auth"})
        except SunWegApiError:
            return self._async_show_user_form(step, {"base": "timeout_connect"})

        return None

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self._async_show_user_form("user")

        # Store authentication info
        self.data = user_input

        conf_result = await self.hass.async_add_executor_job(
            self._set_auth_data,
            "user",
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )

        return await self.async_step_plant() if conf_result is None else conf_result

    async def async_step_plant(self, user_input=None) -> ConfigFlowResult:
        """Handle adding a "plant" to Home Assistant."""
        plant_list = await self.hass.async_add_executor_job(self.api.listPlants)

        if len(plant_list) == 0:
            return self.async_abort(reason="no_plants")

        plants = {plant.id: plant.name for plant in plant_list}

        if user_input is None and len(plant_list) > 1:
            data_schema = vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(plants)})

            return self.async_show_form(step_id="plant", data_schema=data_schema)

        if user_input is None and len(plant_list) == 1:
            user_input = {CONF_PLANT_ID: plant_list[0].id}

        user_input[CONF_NAME] = plants[user_input[CONF_PLANT_ID]]
        await self.async_set_unique_id(user_input[CONF_PLANT_ID])
        self._abort_if_unique_id_configured()
        self.data.update(user_input)
        return self.async_create_entry(title=self.data[CONF_NAME], data=self.data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request from SunWEG."""
        self.data.update(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        if user_input is None:
            return self._async_show_user_form("reauth_confirm")

        self.data.update(user_input)
        conf_result = await self.hass.async_add_executor_job(
            self._set_auth_data,
            "reauth_confirm",
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )
        if conf_result is not None:
            return conf_result

        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is not None:
            data: Mapping[str, Any] = self.data
            self.hass.config_entries.async_update_entry(entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

        return self.async_abort(reason="reauth_successful")
