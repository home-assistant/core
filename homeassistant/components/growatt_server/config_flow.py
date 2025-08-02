"""Config flow for growatt server integration."""

from typing import Any

import growattServer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_AUTH_TYPE,
    DEFAULT_URL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
    SERVER_URLS,
)


class GrowattServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow class."""

    VERSION = 1

    api: growattServer.GrowattApi

    def __init__(self) -> None:
        """Initialise growatt server flow."""
        self.user_id = None
        self.data: dict[str, Any] = {}
        self.auth_type = None
        self.plants: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return await self.async_step_auth_type()

        if self.auth_type == AUTH_API_TOKEN:
            # Using token authentication
            token = user_input[CONF_TOKEN]
            self.api = growattServer.OpenApiV1(token=token)

            # Verify token by fetching plant list
            try:
                plant_response = await self.hass.async_add_executor_job(
                    self.api.plant_list
                )
            except growattServer.GrowattV1ApiError as e:
                # Pass the error message for frontend display
                return self._async_show_user_form(
                    {
                        "base": "invalid_auth",
                        "api_error": getattr(e, "error_msg", str(e)),
                    }
                )

            self.plants = plant_response.get("plants", [])
            if not self.plants:
                return self.async_abort(reason="no_plants")

        else:
            # Traditional username/password authentication
            self.api = growattServer.GrowattApi(
                add_random_user_id=True, agent_identifier=user_input[CONF_USERNAME]
            )
            self.api.server_url = user_input[CONF_URL]
            login_response = await self.hass.async_add_executor_job(
                self.api.login, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            if (
                not login_response["success"]
                and login_response["msg"] == LOGIN_INVALID_AUTH_CODE
            ):
                return self._async_show_user_form({"base": "invalid_auth"})
            self.user_id = login_response["user"]["id"]

        self.data = user_input
        return await self.async_step_plant()

    async def async_step_auth_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose authentication method."""
        if user_input is not None:
            self.auth_type = user_input[CONF_AUTH_TYPE]
            return self._async_show_user_form()

        return self.async_show_form(
            step_id="auth_type",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_TYPE, default=DEFAULT_AUTH_TYPE): vol.In(
                        {
                            AUTH_PASSWORD: "Username & Password",
                            AUTH_API_TOKEN: "API Token",
                        }
                    )
                }
            ),
            description_placeholders={
                "note": "Token authentication only supports MIN/TLX devices. For other device types, please use username/password authentication."
            },
        )

    @callback
    def _async_show_user_form(
        self, errors: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the form to the user."""
        if self.auth_type == AUTH_API_TOKEN:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_URL, default=DEFAULT_URL): vol.In(SERVER_URLS),
                }
            )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle adding a "plant" to Home Assistant."""
        if self.auth_type == AUTH_API_TOKEN:
            # Using V1 API with token
            if not self.plants:
                return self.async_abort(reason="no_plants")

            # Create dictionary of plant_id -> name
            plant_dict = {}
            for plant in self.plants:
                plant_id = str(plant.get("plant_id", ""))
                plant_name = plant.get("name", "Unknown Plant")
                if plant_id:
                    plant_dict[plant_id] = plant_name

            if user_input is None and len(plant_dict) > 1:
                data_schema = vol.Schema(
                    {vol.Required(CONF_PLANT_ID): vol.In(plant_dict)}
                )
                return self.async_show_form(step_id="plant", data_schema=data_schema)

            if user_input is None:
                # Single plant => mark it as selected
                user_input = {CONF_PLANT_ID: list(plant_dict.keys())[0]}

            user_input[CONF_NAME] = plant_dict[user_input[CONF_PLANT_ID]]
            user_input[CONF_AUTH_TYPE] = self.auth_type

            # Include token in the final config data
            if CONF_TOKEN in self.data:
                user_input[CONF_TOKEN] = self.data[CONF_TOKEN]
        else:
            # Traditional API
            plant_info = await self.hass.async_add_executor_job(
                self.api.plant_list, self.user_id
            )

            if not plant_info["data"]:
                return self.async_abort(reason="no_plants")

            plants = {
                plant["plantId"]: plant["plantName"] for plant in plant_info["data"]
            }

            if user_input is None and len(plant_info["data"]) > 1:
                data_schema = vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(plants)})
                return self.async_show_form(step_id="plant", data_schema=data_schema)

            if user_input is None:
                # single plant => mark it as selected
                user_input = {CONF_PLANT_ID: plant_info["data"][0]["plantId"]}

            user_input[CONF_NAME] = plants[user_input[CONF_PLANT_ID]]
            user_input[CONF_AUTH_TYPE] = self.auth_type

        await self.async_set_unique_id(user_input[CONF_PLANT_ID])
        self._abort_if_unique_id_configured()
        self.data.update(user_input)
        return self.async_create_entry(title=self.data[CONF_NAME], data=self.data)
