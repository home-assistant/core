"""Config flow to configure Heos."""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pyheos import Heos, HeosError
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return f"Controller ({host})"


class HeosFlowHandler(ConfigFlow, domain=DOMAIN):
    """Define a flow for HEOS."""

    VERSION = 1

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Heos device."""
        # Store discovered host
        if TYPE_CHECKING:
            assert discovery_info.ssdp_location
        hostname = urlparse(discovery_info.ssdp_location).hostname
        friendly_name = (
            f"{discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]} ({hostname})"
        )
        self.hass.data.setdefault(DOMAIN, {})
        self.hass.data[DOMAIN][friendly_name] = hostname
        await self.async_set_unique_id(DOMAIN)
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Obtain host and validate connection."""
        self.hass.data.setdefault(DOMAIN, {})
        await self.async_set_unique_id(DOMAIN)
        # Try connecting to host if provided
        errors = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            # Map host from friendly name if in discovered hosts
            host = self.hass.data[DOMAIN].get(host, host)
            heos = Heos(host)
            try:
                await heos.connect()
                self.hass.data.pop(DOMAIN)
                return self.async_create_entry(
                    title=format_title(host), data={CONF_HOST: host}
                )
            except HeosError:
                errors[CONF_HOST] = "cannot_connect"
            finally:
                await heos.disconnect()

        # Return form
        host_type = (
            str if not self.hass.data[DOMAIN] else vol.In(list(self.hass.data[DOMAIN]))
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): host_type}),
            errors=errors,
        )
