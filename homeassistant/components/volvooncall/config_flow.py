"""Config Flow Handler for volvooncall."""
import voluptuous as vol
from volvooncall import Connection

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import VolvoData
from .const import CONF_MUTABLE, CONF_SCANDINAVIAN_MILES, DOMAIN
from .errors import AuthenticationError, InvalidRegionError

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_REGION): cv.string,
        vol.Optional(CONF_MUTABLE, default=True): cv.boolean,
        vol.Optional(CONF_SCANDINAVIAN_MILES, default=False): cv.boolean,
    },
)


class VolvoOnCallConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """VolvoOnCall config flow."""

    VERSION = 1
    data = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle user step."""
        errors = {}
        if user_input is not None:
            try:
                await self.is_valid(user_input)
            except InvalidRegionError:
                errors[CONF_REGION] = "invalid_region"
            except AuthenticationError:
                errors["base"] = "auth"
            if not errors:
                self.data = user_input
                return self.async_create_entry(title="Volvo On Call", data=self.data)

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data) -> FlowResult:
        """Import volvooncall config from configuration.yaml."""
        import_result = await self.async_step_user(import_data)

        if import_result.get("errors") is None:
            notification_data = {}
            notification_data["title"] = "Volvo On Call Migration Complete"
            notification_data[
                "message"
            ] = "Your Volvo On Call configuration has been migrated to the Settings UI. Please remove your volvooncall YAML configuration."
            await self.hass.services.async_call(
                "persistent_notification", "create", notification_data
            )

        return import_result

    async def is_valid(self, user_input):
        """Check for user input errors."""
        if CONF_REGION not in user_input.keys():
            user_input[CONF_REGION] = None

        if (
            user_input[CONF_REGION] is not None
            and user_input[CONF_REGION] != "na"
            and user_input[CONF_REGION] != "cn"
        ):
            raise InvalidRegionError

        session = async_get_clientsession(self.hass)

        connection = Connection(
            session=session,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            service_url=None,
            region=user_input[CONF_REGION],
        )

        test_volvo_data = VolvoData(self.hass, connection, user_input)

        return await test_volvo_data.auth_is_valid()
