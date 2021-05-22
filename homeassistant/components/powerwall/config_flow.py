"""Config flow for Tesla Powerwall integration."""
import logging

from tesla_powerwall import (
    AccessDeniedError,
    MissingAttributeError,
    Powerwall,
    PowerwallUnreachableError,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _login_and_fetch_site_info(power_wall: Powerwall, password: str):
    """Login to the powerwall and fetch the base info."""
    if password is not None:
        power_wall.login(password)
    power_wall.detect_and_pin_version()
    return power_wall.get_site_info()


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """

    power_wall = Powerwall(data[CONF_IP_ADDRESS])
    password = data[CONF_PASSWORD]

    try:
        site_info = await hass.async_add_executor_job(
            _login_and_fetch_site_info, power_wall, password
        )
    except MissingAttributeError as err:
        # Only log the exception without the traceback
        _LOGGER.error(str(err))
        raise WrongVersion from err

    # Return info that you want to store in the config entry.
    return {"title": site_info.site_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1

    def __init__(self):
        """Initialize the powerwall flow."""
        self.ip_address = None

    async def async_step_dhcp(self, discovery_info):
        """Handle dhcp discovery."""
        self.ip_address = discovery_info[IP_ADDRESS]
        self._async_abort_entries_match({CONF_IP_ADDRESS: self.ip_address})
        self.ip_address = discovery_info[IP_ADDRESS]
        self.context["title_placeholders"] = {CONF_IP_ADDRESS: self.ip_address}
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except PowerwallUnreachableError:
                errors[CONF_IP_ADDRESS] = "cannot_connect"
            except WrongVersion:
                errors["base"] = "wrong_version"
            except AccessDeniedError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                existing_entry = await self.async_set_unique_id(
                    user_input[CONF_IP_ADDRESS]
                )
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS, default=self.ip_address): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, data):
        """Handle configuration by re-auth."""
        self.ip_address = data[CONF_IP_ADDRESS]
        return await self.async_step_user()


class WrongVersion(exceptions.HomeAssistantError):
    """Error to indicate the powerwall uses a software version we cannot interact with."""
