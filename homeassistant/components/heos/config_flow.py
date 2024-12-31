"""Config flow to configure Heos."""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pyheos import Heos, HeosError, HeosOptions
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return f"HEOS System (via {host})"


async def _validate_host(host: str, errors: dict[str, str]) -> bool:
    """Validate host is reachable, return True, otherwise populate errors and return False."""
    heos = Heos(HeosOptions(host, events=False, heart_beat=False))
    try:
        await heos.connect()
    except HeosError:
        errors[CONF_HOST] = "cannot_connect"
        return False
    finally:
        await heos.disconnect()
    return True


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
        errors: dict[str, str] = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            # Map host from friendly name if in discovered hosts
            host = self.hass.data[DOMAIN].get(host, host)
            if await _validate_host(host, errors):
                self.hass.data.pop(DOMAIN)  # Remove discovery data
                return self.async_create_entry(
                    title=format_title(host), data={CONF_HOST: host}
                )

        # Return form
        host_type = (
            str if not self.hass.data[DOMAIN] else vol.In(list(self.hass.data[DOMAIN]))
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): host_type}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow reconfiguration of entry."""
        entry = self._get_reconfigure_entry()
        host = entry.data[CONF_HOST]  # Get current host value
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if await _validate_host(host, errors):
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
            errors=errors,
        )
