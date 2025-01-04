"""Config flow to configure Heos."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from pyheos import CommandFailedError, Heos, HeosError, HeosOptions
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


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


async def _validate_auth(
    user_input: dict[str, str], heos: Heos, errors: dict[str, str]
) -> bool:
    """Validate authentication by signing in or out, otherwise populate errors if needed."""
    if not user_input:
        # Log out (neither username nor password provided)
        try:
            await heos.sign_out()
        except HeosError:
            errors["base"] = "unknown"
            _LOGGER.exception("Unexpected error occurred during sign-out")
            return False
        else:
            _LOGGER.debug("Successfully signed-out of HEOS Account")
            return True

    # Ensure both username and password are provided
    authentication = CONF_USERNAME in user_input or CONF_PASSWORD in user_input
    if authentication and CONF_USERNAME not in user_input:
        errors[CONF_USERNAME] = "username_missing"
        return False
    if authentication and CONF_PASSWORD not in user_input:
        errors[CONF_PASSWORD] = "password_missing"
        return False

    # Attempt to login (both username and password provided)
    try:
        await heos.sign_in(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
    except CommandFailedError as err:
        if err.error_id in (6, 8, 10):  # Auth-specific errors
            errors["base"] = "invalid_auth"
            _LOGGER.warning("Failed to sign-in to HEOS Account: %s", err)
        else:
            errors["base"] = "unknown"
            _LOGGER.exception("Unexpected error occurred during sign-in")
        return False
    except HeosError:
        errors["base"] = "unknown"
        _LOGGER.exception("Unexpected error occurred during sign-in")
        return False
    else:
        _LOGGER.debug(
            "Successfully signed-in to HEOS Account: %s",
            heos.signed_in_username,
        )
        return True


class HeosFlowHandler(ConfigFlow, domain=DOMAIN):
    """Define a flow for HEOS."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return HeosOptionsFlowHandler()

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication after auth failure event."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate account credentials and update options."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            heos = cast(Heos, entry.runtime_data.controller_manager.controller)
            if await _validate_auth(user_input, heos, errors):
                return self.async_update_reload_and_abort(entry, options=user_input)

        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=self.add_suggested_values_to_schema(
                AUTH_SCHEMA, user_input or entry.options
            ),
        )


class HeosOptionsFlowHandler(OptionsFlow):
    """Define HEOS options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            heos = cast(
                Heos, self.config_entry.runtime_data.controller_manager.controller
            )
            if await _validate_auth(user_input, heos, errors):
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            errors=errors,
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                AUTH_SCHEMA, user_input or self.config_entry.options
            ),
        )
