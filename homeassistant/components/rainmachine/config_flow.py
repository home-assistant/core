"""Config flow to configure the RainMachine component."""
from regenmaschine import Client
from regenmaschine.errors import RainMachineError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_ZONE_RUN_TIME, DEFAULT_PORT, DEFAULT_ZONE_RUN, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


def get_client_controller(client):
    """Enumerate controllers to find the first mac."""
    for controller in client.controllers.values():
        return controller


async def async_get_controller(hass, ip_address, password, port, ssl):
    """Auth and fetch the mac address from the controller."""
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(session=websession)
    try:
        await client.load_local(ip_address, password, port=port, ssl=ssl)
    except RainMachineError:
        return None
    else:
        return get_client_controller(client)


class RainMachineFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a RainMachine config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.discovered_ip_address = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return RainMachineOptionsFlowHandler(config_entry)

    @callback
    def _async_abort_ip_address_configured(self, ip_address):
        """Abort if we already have an entry for the ip."""
        # IP already configured
        for entry in self._async_current_entries(include_ignore=False):
            if ip_address in entry.data[CONF_IP_ADDRESS]:
                raise AbortFlow("already_configured")

    async def async_step_homekit(self, discovery_info):
        """Handle a flow initialized by homekit discovery."""
        return await self.async_step_zeroconf(discovery_info)

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle discovery via zeroconf."""
        ip_address = discovery_info["host"]

        self._async_abort_ip_address_configured(ip_address)
        # Handle IP change
        for entry in self._async_current_entries(include_ignore=False):
            # Try our existing credentials to check for ip change
            if controller := await async_get_controller(
                self.hass,
                ip_address,
                entry.data[CONF_PASSWORD],
                entry.data[CONF_PORT],
                entry.data.get(CONF_SSL, True),
            ):
                await self.async_set_unique_id(controller.mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_IP_ADDRESS: ip_address}
                )

        # A new rain machine, we will change out the unique id
        # for the mac address once we authenticate, however we want to
        # prevent multiple different rain machines on the same network
        # from being shown in discovery
        await self.async_set_unique_id(ip_address)
        self._abort_if_unique_id_configured()
        self.discovered_ip_address = ip_address
        return await self.async_step_user()

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        return vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS, default=self.discovered_ip_address): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}
        if user_input:
            self._async_abort_ip_address_configured(user_input[CONF_IP_ADDRESS])
            controller = await async_get_controller(
                self.hass,
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_PASSWORD],
                user_input[CONF_PORT],
                user_input.get(CONF_SSL, True),
            )
            if controller:
                await self.async_set_unique_id(controller.mac)
                self._abort_if_unique_id_configured()

                # Unfortunately, RainMachine doesn't provide a way to refresh the
                # access token without using the IP address and password, so we have to
                # store it:
                return self.async_create_entry(
                    title=controller.name,
                    data={
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_SSL: user_input.get(CONF_SSL, True),
                        CONF_ZONE_RUN_TIME: user_input.get(
                            CONF_ZONE_RUN_TIME, DEFAULT_ZONE_RUN
                        ),
                    },
                )

            errors = {CONF_PASSWORD: "invalid_auth"}

        if self.discovered_ip_address:
            self.context["title_placeholders"] = {"ip": self.discovered_ip_address}
        return self.async_show_form(
            step_id="user", data_schema=self._async_generate_schema(), errors=errors
        )


class RainMachineOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a RainMachine options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ZONE_RUN_TIME,
                        default=self.config_entry.options.get(CONF_ZONE_RUN_TIME),
                    ): cv.positive_int
                }
            ),
        )
