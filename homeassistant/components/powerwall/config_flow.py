"""Config flow for Tesla Powerwall integration."""
import logging

from tesla_powerwall import MissingAttributeError, Powerwall, PowerwallUnreachableError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import callback

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """

    power_wall = Powerwall(data[CONF_IP_ADDRESS])

    try:
        await hass.async_add_executor_job(power_wall.detect_and_pin_version)
        site_info = await hass.async_add_executor_job(power_wall.get_site_info)
    except PowerwallUnreachableError as err:
        raise CannotConnect from err
    except MissingAttributeError as err:
        # Only log the exception without the traceback
        _LOGGER.error(str(err))
        raise WrongVersion from err

    # Return info that you want to store in the config entry.
    return {"title": site_info.site_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the powerwall flow."""
        self.ip_address = None

    async def async_step_dhcp(self, dhcp_discovery):
        """Handle dhcp discovery."""
        if self._async_ip_address_already_configured(dhcp_discovery[IP_ADDRESS]):
            return self.async_abort(reason="already_configured")

        self.ip_address = dhcp_discovery[IP_ADDRESS]
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {CONF_IP_ADDRESS: self.ip_address}
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except WrongVersion:
                errors["base"] = "wrong_version"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_IP_ADDRESS, default=self.ip_address): str}
            ),
            errors=errors,
        )

    @callback
    def _async_ip_address_already_configured(self, ip_address):
        """See if we already have an entry matching the ip_address."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_IP_ADDRESS) == ip_address:
                return True
        return False


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class WrongVersion(exceptions.HomeAssistantError):
    """Error to indicate the powerwall uses a software version we cannot interact with."""
