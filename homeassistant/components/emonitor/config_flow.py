"""Config flow for SiteSage Emonitor integration."""

import logging

from aioemonitor import Emonitor
import aiohttp
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import format_mac

from . import name_short_mac
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def fetch_mac_and_title(hass: HomeAssistant, host):
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_get_clientsession(hass)
    emonitor = Emonitor(host, session)
    status = await emonitor.async_get_status()
    mac_address = status.network.mac_address
    return {"title": name_short_mac(mac_address[-6:]), "mac_address": mac_address}


class EmonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SiteSage Emonitor."""

    VERSION = 1

    def __init__(self):
        """Initialize Emonitor ConfigFlow."""
        self.discovered_ip = None
        self.discovered_info = None

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
                await self.async_set_unique_id(
                    format_mac(info["mac_address"]), raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("host", default=self.discovered_ip): str}
            ),
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        self.discovered_ip = discovery_info.ip
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: self.discovered_ip})
        name = name_short_mac(short_mac(discovery_info.macaddress))
        self.context["title_placeholders"] = {"name": name}
        try:
            self.discovered_info = await fetch_mac_and_title(
                self.hass, self.discovered_ip
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(
                "Unable to fetch status, falling back to manual entry", exc_info=ex
            )
            return await self.async_step_user()
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Attempt to confirm."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.discovered_info["title"],
                data={CONF_HOST: self.discovered_ip},
            )

        self._set_confirm_only()
        self.context["title_placeholders"] = {"name": self.discovered_info["title"]}
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                CONF_HOST: self.discovered_ip,
                CONF_NAME: self.discovered_info["title"],
            },
        )


def short_mac(mac):
    """Short version of the mac."""
    return "".join(mac.split(":")[3:]).upper()
