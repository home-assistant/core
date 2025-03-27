"""Config flow to configure Heos."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from pyheos import (
    CommandAuthenticationError,
    ConnectionState,
    Heos,
    HeosError,
    HeosOptions,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, ENTRY_TITLE
from .coordinator import HeosConfigEntry

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


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
    user_input: dict[str, str], entry: HeosConfigEntry, errors: dict[str, str]
) -> bool:
    """Validate authentication by signing in or out, otherwise populate errors if needed."""
    can_validate = (
        hasattr(entry, "runtime_data")
        and entry.runtime_data.heos.connection_state is ConnectionState.CONNECTED
    )
    if not user_input:
        # Log out (neither username nor password provided)
        if not can_validate:
            return True
        try:
            await entry.runtime_data.heos.sign_out()
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
    if not can_validate:
        return True
    try:
        await entry.runtime_data.heos.sign_in(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )
    except CommandAuthenticationError as err:
        errors["base"] = "invalid_auth"
        _LOGGER.warning("Failed to sign-in to HEOS Account: %s", err)
        return False
    except HeosError:
        errors["base"] = "unknown"
        _LOGGER.exception("Unexpected error occurred during sign-in")
        return False
    else:
        _LOGGER.debug(
            "Successfully signed-in to HEOS Account: %s",
            entry.runtime_data.heos.signed_in_username,
        )
        return True


def _get_current_hosts(entry: HeosConfigEntry) -> set[str]:
    """Get a set of current hosts from the entry."""
    hosts = set(entry.data[CONF_HOST])
    if hasattr(entry, "runtime_data"):
        hosts.update(
            player.ip_address
            for player in entry.runtime_data.heos.players.values()
            if player.ip_address is not None
        )
    return hosts


class HeosFlowHandler(ConfigFlow, domain=DOMAIN):
    """Define a flow for HEOS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the HEOS flow."""
        self._discovered_host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: HeosConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return HeosOptionsFlowHandler()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Heos device."""
        # Store discovered host
        if TYPE_CHECKING:
            assert discovery_info.ssdp_location

        entry: HeosConfigEntry | None = await self.async_set_unique_id(DOMAIN)
        hostname = urlparse(discovery_info.ssdp_location).hostname
        assert hostname is not None

        # Abort early when discovery is ignored or host is part of the current system
        if entry and (
            entry.source == SOURCE_IGNORE or hostname in _get_current_hosts(entry)
        ):
            return self.async_abort(reason="single_instance_allowed")

        # Connect to discovered host and get system information
        heos = Heos(HeosOptions(hostname, events=False, heart_beat=False))
        try:
            await heos.connect()
            system_info = await heos.get_system_info()
        except HeosError as error:
            _LOGGER.debug(
                "Failed to retrieve system information from discovered HEOS device %s",
                hostname,
                exc_info=error,
            )
            return self.async_abort(reason="cannot_connect")
        finally:
            await heos.disconnect()

        # Select the preferred host, if available
        if system_info.preferred_hosts:
            hostname = system_info.preferred_hosts[0].ip_address

        # Move to confirmation when not configured
        if entry is None:
            self._discovered_host = hostname
            return await self.async_step_confirm_discovery()

        # Only update if the configured host isn't part of the discovered hosts to ensure new players that come online don't trigger a reload
        if entry.data[CONF_HOST] not in [host.ip_address for host in system_info.hosts]:
            _LOGGER.debug(
                "Updated host %s to discovered host %s", entry.data[CONF_HOST], hostname
            )
            return self.async_update_reload_and_abort(
                entry,
                data_updates={CONF_HOST: hostname},
                reason="reconfigure_successful",
            )
        return self.async_abort(reason="single_instance_allowed")

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered HEOS system."""
        if user_input is not None:
            assert self._discovered_host is not None
            return self.async_create_entry(
                title=ENTRY_TITLE, data={CONF_HOST: self._discovered_host}
            )

        self._set_confirm_only()
        return self.async_show_form(step_id="confirm_discovery")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Obtain host and validate connection."""
        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
        self._abort_if_unique_id_configured(error="single_instance_allowed")
        # Try connecting to host if provided
        errors: dict[str, str] = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            if await _validate_host(host, errors):
                return self.async_create_entry(
                    title=ENTRY_TITLE, data={CONF_HOST: host}
                )

        # Return form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
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
        entry: HeosConfigEntry = self._get_reauth_entry()
        if user_input is not None:
            if await _validate_auth(user_input, entry, errors):
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
            if await _validate_auth(user_input, self.config_entry, errors):
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            errors=errors,
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                AUTH_SCHEMA, user_input or self.config_entry.options
            ),
        )
