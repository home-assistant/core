"""Config flow for Subaru integration."""
from datetime import datetime
import logging

from subarulink import (
    Controller as SubaruAPI,
    InvalidCredentials,
    InvalidPIN,
    SubaruException,
)
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_HARD_POLL_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured Subaru instances."""
    return {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}


class SubaruConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Subaru."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        error = None

        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                        vol.Required(CONF_PIN): str,
                    }
                ),
            )

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return self.async_abort(reason="already_configured")

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidCredentials:
            error = {"base": "invalid_auth"}
        except InvalidPIN:
            error = {"base": "invalid_pin"}
        except SubaruException as ex:
            _LOGGER.error("Unable to communicate with Subaru API: %s", ex.message)
            return self.async_abort(reason="cannot_connect")

        if error:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                        ): str,
                        vol.Required(
                            CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)
                        ): str,
                        vol.Required(CONF_PIN, default=user_input.get(CONF_PIN)): str,
                    }
                ),
                errors=error,
            )

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=info)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Subaru."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_HARD_POLL_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_HARD_POLL_INTERVAL, DEFAULT_HARD_POLL_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_HARD_POLL_INTERVAL)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    data: contains values provided by the user.
    """
    websession = aiohttp_client.async_get_clientsession(hass)
    now = datetime.now()
    if not data.get(CONF_DEVICE_ID):
        data[CONF_DEVICE_ID] = int(now.timestamp())
    date = now.strftime("%Y-%m-%d")
    device_name = "Home Assistant: Added " + date

    controller = SubaruAPI(
        websession,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        device_id=data[CONF_DEVICE_ID],
        pin=data[CONF_PIN],
        device_name=device_name,
    )
    _LOGGER.info(
        "Setting up first time connection to Subuaru API.  This may take up to 20 seconds."
    )
    if await controller.connect():
        _LOGGER.debug("Successfully authenticated and authorized with Subaru API")

    _LOGGER.debug("Testing user provided PIN with Subaru remote service requests")
    if await controller.test_pin():
        _LOGGER.debug("User provided PIN is valid for Subaru remote service requests")
    else:
        _LOGGER.info(
            "No active remote service subscription, PIN number will not be used"
        )

    return data
