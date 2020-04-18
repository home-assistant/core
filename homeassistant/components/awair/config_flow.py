"""Config flow for Awair."""

from typing import Union

from python_awair import Awair
from python_awair.exceptions import AuthError, AwairError
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER  # pylint: disable=unused-import


class AwairFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Awair."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Set up the Awair configuration flow."""
        self._errors = {}

    async def async_step_user(self, user_input: Union[dict, None] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            awair = Awair(access_token=user_input[CONF_ACCESS_TOKEN], session=session)
            try:
                user = await awair.user()
                devices = await user.devices()
                if not devices:
                    return self.async_abort(reason="no_devices")

            except AuthError:
                self._errors[CONF_ACCESS_TOKEN] = "auth"
            except AwairError as err:
                LOGGER.error("Unexpected API error: %s", err)
                self._errors["base"] = "unknown"

            if not self._errors:
                unique_id = f"awair-{user_input[CONF_ACCESS_TOKEN]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = f"{user.email} ({user.user_id})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=self._errors,
        )
