"""Config flow for SiteSage Emonitor integration."""
import logging

from aioemonitor import Emonitor
import aiohttp
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def fetch_mac_and_title(hass: core.HomeAssistant, host):
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_get_clientsession(hass)
    emonitor = Emonitor(host, session)
    status = await emonitor.async_get_status()
    mac_address = status.network.mac_address
    # Return info that you want to store in the config entry.
    return {"title": f"Emonitor {mac_address[-6:]}", "mac_address": mac_address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SiteSage Emonitor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize Emonitor ConfigFlow."""
        self.discovered_ip = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await fetch_mac_and_title(self.hass, user_input[CONF_HOST])
            except aiohttp.ClientError:
                errors[CONF_HOST] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(format_mac(info["mac_address"]))
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("host", default=self.discovered_ip): str}
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, dhcp_discovery):
        """Handle dhcp discovery."""
        mac_address = dhcp_discovery[MAC_ADDRESS]
        await self.async_set_unique_id(format_mac(mac_address))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: dhcp_discovery[IP_ADDRESS]}
        )
        self.discovered_ip = dhcp_discovery[IP_ADDRESS]
        self.context["title_placeholders"] = {"name": f"Emonitor {mac_address[-6:]}"}
        return await self.async_step_user()
