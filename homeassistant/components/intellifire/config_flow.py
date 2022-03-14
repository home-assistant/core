"""Config flow for IntelliFire integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientConnectionError
from intellifire4py import (
    AsyncUDPFireplaceFinder,
    IntellifireAsync,
    IntellifireControlAsync,
)
from intellifire4py.control import LoginException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERIAL, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})

MANUAL_ENTRY_STRING = "IP Address"  # Simplified so it does not have to be translated


async def validate_host_input(host: str) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = IntellifireAsync(host)
    await api.poll()
    serial = api.data.serial
    LOGGER.debug("Found a fireplace: %s", serial)
    # Return the serial number which will be used to calculate a unique ID for the device/sensors
    return serial


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliFire."""

    VERSION = 2

    def __init__(self):
        """Initialize the Config Flow Handler."""
        self._config_context = {}
        self._not_configured_hosts: list[str] = []

    async def _find_fireplaces(self):
        """Perform UDP discovery."""
        fireplace_finder = AsyncUDPFireplaceFinder()
        discovered_hosts = await fireplace_finder.search_fireplace(timeout=1)
        configured_hosts = {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data  # CONF_HOST will be missing for ignored entries
        }

        self._not_configured_hosts = [
            ip for ip in discovered_hosts if ip not in configured_hosts
        ]
        LOGGER.debug("Discovered Hosts: %s", discovered_hosts)
        LOGGER.debug("Configured Hosts: %s", configured_hosts)
        LOGGER.debug("Not Configured Hosts: %s", self._not_configured_hosts)

    async def validate_api_access_and_create(self, user_input: dict[str, Any]):
        """Validate username/password against api."""

        ift_control = IntellifireControlAsync(fireplace_ip=user_input[CONF_HOST])

        try:
            await ift_control.login(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            await ift_control.get_username()
        finally:
            await ift_control.close()

        # Create stuff now
        return self.async_create_entry(
            title=f"Fireplace {user_input[CONF_SERIAL]}",
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
        )

    async def async_step_api_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure API access."""
        errors = {}

        control_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is not None:

            control_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            )

            if user_input[CONF_USERNAME] != "":
                try:
                    # Update config context & validate
                    self._config_context[CONF_USERNAME] = user_input[CONF_USERNAME]
                    self._config_context[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                    return await self.validate_api_access_and_create(
                        self._config_context
                    )
                except (ConnectionError, ClientConnectionError):
                    errors["base"] = "iftapi_connect"
                except LoginException:
                    errors["base"] = "api_error"

        return self.async_show_form(
            step_id="api_token", errors=errors, data_schema=control_schema
        )

    async def _async_validate_api_and_create(
        self, host: str, username: str, password: str, serial: str
    ) -> FlowResult:
        pass

    async def _async_validate_ip_and_continue(self, host: str) -> FlowResult:
        """Validate local config and continue."""
        self._async_abort_entries_match({CONF_HOST: host})
        serial = await validate_host_input(host)
        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store current data and jump to next stage
        self._config_context = {CONF_HOST: host, CONF_SERIAL: serial}

        return await self.async_step_api_token()

    async def async_step_manual_device_entry(self, user_input=None):
        """Handle manual input of local IP configuration."""
        errors = {}
        host = user_input.get(CONF_HOST) if user_input else None
        if user_input is not None:
            try:
                return await self._async_validate_ip_and_continue(host)
            except (ConnectionError, ClientConnectionError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual_device_entry",
            errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): str}),
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick which device to configure."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_HOST] == MANUAL_ENTRY_STRING:
                return await self.async_step_manual_device_entry()

            try:
                return await self._async_validate_ip_and_continue(user_input[CONF_HOST])
            except (ConnectionError, ClientConnectionError):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="pick_device",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): vol.In(
                        self._not_configured_hosts + [MANUAL_ENTRY_STRING]
                    )
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the user flow."""

        # Launch fireplaces discovery
        await self._find_fireplaces()

        if self._not_configured_hosts:
            LOGGER.debug("Running Step: pick_device")
            return await self.async_step_pick_device()
        LOGGER.debug("Running Step: manual_device_entry")
        return await self.async_step_manual_device_entry()

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_api_token()
