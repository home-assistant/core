"""Config flow for Elexa Guardian integration."""
from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from .const import CONF_UID, DOMAIN, LOGGER  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_IP_ADDRESS): str, vol.Required(CONF_PORT, default=7777): int}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    async with Client(data[CONF_IP_ADDRESS]) as client:
        ping_data = await client.device.ping()

    return {
        "title": f"Elexa Guardian ({data[CONF_IP_ADDRESS]})",
        CONF_UID: ping_data["data"]["uid"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elexa Guardian."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.discovery_info = {}

    async def async_step_user(self, user_input=None):
        """Handle configuration via the UI."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={}
            )

        await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
        self._abort_if_unique_id_configured()

        try:
            info = await validate_input(self.hass, user_input)
        except GuardianError as err:
            LOGGER.error("Error while connecting to unit: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={CONF_IP_ADDRESS: "cannot_connect"},
            )

        return self.async_create_entry(
            title=info["title"], data={CONF_UID: info["uid"], **user_input}
        )

    async def async_step_zeroconf(self, discovery_info=None):
        """Handle the configuration via zeroconf."""
        if discovery_info is None:
            return self.async_abort(reason="connection_error")

        ip_address = discovery_info["host"]

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context[CONF_IP_ADDRESS] = ip_address

        if any(
            ip_address == flow["context"][CONF_IP_ADDRESS]
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        self.discovery_info = {
            CONF_IP_ADDRESS: ip_address,
            CONF_PORT: discovery_info["port"],
        }

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Finish the configuration via zeroconf."""
        if user_input is None:
            return self.async_show_form(step_id="zeroconf_confirm")
        return await self.async_step_user(self.discovery_info)
