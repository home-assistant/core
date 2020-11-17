"""Config flow for FireServiceRota."""
from pyfireservicerota import FireServiceRota, InvalidAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME

from .const import DOMAIN, URL_LIST  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="www.brandweerrooster.nl"): vol.In(URL_LIST),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class FireServiceRotaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a FireServiceRota config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            try:
                api = FireServiceRota(
                    base_url=user_input[CONF_URL],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                token_info = await self.hass.async_add_executor_job(api.request_tokens)

            except InvalidAuthError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "invalid_auth"},
                )

            return self.async_create_entry(
                title=user_input[CONF_USERNAME],
                data={
                    "auth_implementation": DOMAIN,
                    CONF_URL: user_input[CONF_URL],
                    CONF_TOKEN: token_info,
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    # async def async_step_reauth(self, user_input=None):
    #     """Handle the start of the config flow."""
    #     errors = {}
    #     if user_input is not None:
    #         await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
    #         # self._abort_if_unique_id_configured()
    # async def async_step_reauth(self, user_input=None):
    #     """Handle the start of the config flow."""
    #     errors = {}
    #     if user_input is not None:
    #         await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
    #         # self._abort_if_unique_id_configured()

    #         try:
    #             api = FireServiceRota(
    #                 base_url=f"https://{user_input[CONF_URL]}",
    #                 username=user_input[CONF_USERNAME],
    #                 password=user_input[CONF_PASSWORD],
    #             )
    #             token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #         except InvalidAuthError:
    #             return self.async_show_form(
    #                 step_id="reauth",
    #                 data_schema=DATA_SCHEMA,
    #                 errors={"base": "invalid_auth"},
    #             )

    #         return self.async_create_entry(
    #             title=user_input[CONF_USERNAME],
    #             data={
    #                 "auth_implementation": DOMAIN,
    #                 CONF_URL: user_input[CONF_URL],
    #                 CONF_TOKEN: token_info,
    #             },
    #         )

    #     return self.async_show_form(
    #         step_id="reauth", data_schema=DATA_SCHEMA, errors=errors
    #     )

    #             api = FireServiceRota(
    #                 base_url=f"https://{user_input[CONF_URL]}",
    #                 username=user_input[CONF_USERNAME],
    #                 password=user_input[CONF_PASSWORD],
    #             )
    #             token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #         except InvalidAuthError:
    #             return self.async_show_form(
    #                 step_id="reauth",
    #                 data_schema=DATA_SCHEMA,
    #                 errors={"base": "invalid_auth"},
    #             )

    #         return self.async_create_entry(
    #             title=user_input[CONF_USERNAME],
    #             data={
    #                 "auth_implementation": DOMAIN,
    #                 CONF_URL: user_input[CONF_URL],
    #                 CONF_TOKEN: token_info,
    #             },
    #         )

    #     return self.async_show_form(
    #         step_id="reauth", data_schema=DATA_SCHEMA, errors=errors
    #     )

    # async def validate_input(self, user_input):
    #     """Validate form input."""
    #     errors = {}
    #     token_info = None

    #     try:
    #         api = FireServiceRota(
    #             base_url=f"https://{user_input[CONF_URL]}",
    #             username=user_input[CONF_USERNAME],
    #             password=user_input[CONF_PASSWORD],
    #         )
    #         token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #     except InvalidAuthError:
    #         errors = {"base": "invalid_auth"}

    #     return token_info, errors

    # async def async_step_reauth(self, user_input: Optional[dict] = None):
    #     """Handle re-auth if login is invalid."""
    #     errors = {}

    #     if user_input is not None:
    #         token_info, errors = await self.validate_input(user_input)

    #         if not errors:
    #             for entry in self._async_current_entries():
    #                 if entry.unique_id == self.unique_id:
    #                     self.hass.config_entries.async_update_entry(
    #                         entry,
    #                         data={
    #                             CONF_TOKEN: token_info,
    #                         },
    #                     )

    #                     return self.async_abort(reason="reauth_successful")

    #         if errors["base"] != "invalid_auth":
    #             return self.async_abort(reason=errors["base"])

    #     return self.async_show_form(
    #         step_id="reauth",
    #         data_schema=DATA_SCHEMA,
    #         errors=errors,
    #     )

    # async def async_step_reauth(self, user_input=None):
    #     """Handle re-auth if token invalid."""
    #     errors = {}
    #     if user_input is not None:
    #         await self.async_set_unique_id(user_input[CONF_USERNAME].lower())

    #         try:
    #             api = FireServiceRota(
    #                 base_url=f"https://{user_input[CONF_URL]}",
    #                 username=user_input[CONF_USERNAME],
    #                 password=user_input[CONF_PASSWORD],
    #             )
    #             token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #         except InvalidAuthError:
    #             return self.async_show_form(
    #                 step_id="reauth",
    #                 data_schema=DATA_SCHEMA,
    #                 errors={"base": "invalid_auth"},
    #             )

    #         # if error != "invalid_access_token":
    #         #     return self.async_abort(reason=error)

    #     return self.async_show_form(
    #         step_id="user", data_schema=DATA_SCHEMA, errors=errors
    #     )

    # conf = {
    #     CONF_API_KEY: user_input[CONF_API_KEY],
    #     CONF_LATITUDE: self._latitude,
    #     CONF_LONGITUDE: self._longitude,
    #     CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
    # }

    # return await self.async_step_geography_finish(
    #     conf, "reauth_confirm", self.api_key_data_schema
    # )

    # async def async_step_reauth(self, user_input=None):
    #     """Handle re-auth if token invalid."""
    #     errors = {}
    #     if user_input is not None:
    #         await self.async_set_unique_id(user_input.data.[CONF_USERNAME].lower())

    #         try:
    #             api = FireServiceRota(
    #                 base_url=f"https://{user_input[CONF_URL]}",
    #                 username=user_input[CONF_USERNAME],
    #                 password=user_input[CONF_PASSWORD],
    #             )
    #             token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #         except InvalidAuthError:
    #             return self.async_show_form(
    #                 step_id="user",
    #                 data_schema=DATA_SCHEMA,
    #                 errors={"base": "invalid_auth"},
    #             )

    #         if errors:
    #             return self.async_abort(reason="invalid_auth")

    #         for entry in self._async_current_entries():
    #             if entry.unique_id == self.unique_id:
    #                 self.hass.config_entries.async_update_entry(
    #                     entry,
    #                     data={
    #                         "auth_implementation": DOMAIN,
    #                         CONF_URL: user_input[CONF_URL],
    #                         CONF_TOKEN: token_info,
    #                     },
    #                 )

    #                 return self.async_abort(reason="reauth_successful")

    #     return self.async_show_form(
    #         step_id="reauth",
    #         data_schema=DATA_SCHEMA,
    #         errors=errors,
    #     )

    # errors = {}
    # _LOGGER.error("data: %s", data)
    # if data is not None:
    #     try:
    #         api = FireServiceRota(
    #             base_url=f"https://{data[CONF_URL]}",
    #         )
    #         token_info = await self.hass.async_add_executor_job(api.request_tokens)

    #     except InvalidAuthError:
    #         return self.async_show_form(
    #             step_id="user",
    #             data_schema=DATA_SCHEMA,
    #             errors={"base": "invalid_auth"},
    #         )

    #     return self.async_create_entry(
    #         title=data[CONF_USERNAME],
    #         data={
    #             "auth_implementation": DOMAIN,
    #             CONF_URL: data[CONF_URL],
    #             CONF_TOKEN: token_info,
    #         },
    #     )

    # return self.async_show_form(
    #     step_id="reauth", data_schema=DATA_SCHEMA, errors=errors
