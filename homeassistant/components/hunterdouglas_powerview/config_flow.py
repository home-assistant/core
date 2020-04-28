"""Config flow for Hunter Douglas PowerView integration."""
import logging

from aiopvapi.helpers.aiorequest import AioRequest
import async_timeout
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import async_get_device_info
from .const import DEVICE_NAME, DEVICE_SERIAL_NUMBER, HUB_EXCEPTIONS
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
HAP_SUFFIX = "._hap._tcp.local."


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    hub_address = data[CONF_HOST]
    websession = async_get_clientsession(hass)

    pv_request = AioRequest(hub_address, loop=hass.loop, websession=websession)

    try:
        async with async_timeout.timeout(10):
            device_info = await async_get_device_info(pv_request)
    except HUB_EXCEPTIONS:
        raise CannotConnect
    if not device_info:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {
        "title": device_info[DEVICE_NAME],
        "unique_id": device_info[DEVICE_SERIAL_NUMBER],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hunter Douglas PowerView."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the powerview config flow."""
        self.powerview_config = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if self._host_already_configured(user_input[CONF_HOST]):
                return self.async_abort(reason="already_configured")
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(info["unique_id"])
                return self.async_create_entry(
                    title=info["title"], data={CONF_HOST: user_input[CONF_HOST]}
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_user(user_input)

    async def async_step_homekit(self, homekit_info):
        """Handle HomeKit discovery."""

        # If we already have the host configured do
        # not open connections to it if we can avoid it.
        if self._host_already_configured(homekit_info[CONF_HOST]):
            return self.async_abort(reason="already_configured")

        try:
            info = await validate_input(self.hass, homekit_info)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(info["unique_id"], raise_on_progress=False)
        self._abort_if_unique_id_configured({CONF_HOST: homekit_info["host"]})

        name = homekit_info["name"]
        if name.endswith(HAP_SUFFIX):
            name = name[: -len(HAP_SUFFIX)]

        self.powerview_config = {
            CONF_HOST: homekit_info["host"],
            CONF_NAME: name,
        }
        return await self.async_step_link()

    async def async_step_link(self, user_input=None):
        """Attempt to link with Powerview."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.powerview_config[CONF_NAME],
                data={CONF_HOST: self.powerview_config[CONF_HOST]},
            )

        return self.async_show_form(
            step_id="link", description_placeholders=self.powerview_config
        )

    def _host_already_configured(self, host):
        """See if we already have a hub with the host address configured."""
        existing_hosts = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        return host in existing_hosts


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
