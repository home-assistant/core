"""Config flow for DoorBird integration."""
from ipaddress import ip_address
import logging
import urllib

from doorbirdpy import DoorBird
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.util.network import is_link_local

from .const import CONF_EVENTS, DOORBIRD_OUI
from .const import DOMAIN  # pylint:disable=unused-import
from .util import get_mac_address_from_doorstation_info

_LOGGER = logging.getLogger(__name__)


def _schema_with_defaults(host=None, name=None):
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_NAME, default=name): str,
        }
    )


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    device = DoorBird(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    try:
        status = await hass.async_add_executor_job(device.ready)
        info = await hass.async_add_executor_job(device.info)
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise InvalidAuth
        raise CannotConnect
    except OSError:
        raise CannotConnect

    if not status[0]:
        raise CannotConnect

    mac_addr = get_mac_address_from_doorstation_info(info)

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_HOST], "mac_addr": mac_addr}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DoorBird."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the DoorBird config flow."""
        self.discovery_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)
            if not errors:
                await self.async_set_unique_id(info["mac_addr"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        data = self.discovery_schema or _schema_with_defaults()
        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(self, discovery_info):
        """Prepare configuration for a discovered doorbird device."""
        macaddress = discovery_info["properties"]["macaddress"]

        if macaddress[:6] != DOORBIRD_OUI:
            return self.async_abort(reason="not_doorbird_device")
        if is_link_local(ip_address(discovery_info[CONF_HOST])):
            return self.async_abort(reason="link_local_address")

        await self.async_set_unique_id(macaddress)

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info[CONF_HOST]}
        )

        chop_ending = "._axis-video._tcp.local."
        friendly_hostname = discovery_info["name"]
        if friendly_hostname.endswith(chop_ending):
            friendly_hostname = friendly_hostname[: -len(chop_ending)]

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            CONF_NAME: friendly_hostname,
            CONF_HOST: discovery_info[CONF_HOST],
        }
        self.discovery_schema = _schema_with_defaults(
            host=discovery_info[CONF_HOST], name=friendly_hostname
        )

        return await self.async_step_user()

    async def async_step_import(self, user_input):
        """Handle import."""
        if user_input:
            info, errors = await self._async_validate_or_error(user_input)
            if not errors:
                await self.async_set_unique_id(
                    info["mac_addr"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
        return await self.async_step_user(user_input)

    async def _async_validate_or_error(self, user_input):
        """Validate doorbird or error."""
        errors = {}
        info = {}
        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return info, errors

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for doorbird."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            events = [event.strip() for event in user_input[CONF_EVENTS].split(",")]

            return self.async_create_entry(title="", data={CONF_EVENTS: events})

        current_events = self.config_entry.options.get(CONF_EVENTS, [])

        # We convert to a comma separated list for the UI
        # since there really isn't anything better
        options_schema = vol.Schema(
            {vol.Optional(CONF_EVENTS, default=", ".join(current_events)): str}
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
