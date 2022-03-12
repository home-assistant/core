"""Config flow for IntelliFire integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientConnectionError
from intellifire4py import AsyncUDPFireplaceFinder, IntellifireAsync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def validate_host_input(host: str) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = IntellifireAsync(host)
    await api.poll()
    ret = api.data.serial
    LOGGER.debug("Found a fireplace: %s", ret)
    # Return the serial number which will be used to calculate a unique ID for the device/sensors
    return ret


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliFire."""

    VERSION = 1

    def __init__(self):
        """Initialize the Config Flow Handler."""
        self._config_context = {}
        self._discovered_hosts: list[str] = []
        self._not_configured_hosts: list[str] = []

    async def _find_fireplaces(self):
        """Perform UDP discovery."""
        fireplace_finder = AsyncUDPFireplaceFinder()
        self._discovered_hosts = await fireplace_finder.search_fireplace(timeout=1)
        configured_hosts = [
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
        ]
        self._not_configured_hosts = [
            ip for ip in self._discovered_hosts if ip not in configured_hosts
        ]
        LOGGER.debug("Discovered Hosts: %s", str(self._discovered_hosts))
        LOGGER.debug("Configured Hosts: %s", str(configured_hosts))
        LOGGER.debug("Not Configured Hosts: %s", str(self._not_configured_hosts))

    async def async_step_local_config(self, user_input=None):
        """Handle local ip configuration."""

        errors = {}
        placeholder = {}
        local_schema = vol.Schema({vol.Required(CONF_HOST): str})

        if user_input is None:

            if self._not_configured_hosts:
                user_input = {CONF_HOST: self._not_configured_hosts[0]}
                local_schema = vol.Schema(
                    {vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str}
                )
            else:
                if self._discovered_hosts:
                    # If there were discoverd hosts AND all got filtered out fire an error message
                    errors["base"] = "already_discovered"
                    LOGGER.debug("All discovered fireplaces have been configured")

        else:
            # There was User Input
            placeholder = {CONF_HOST: user_input[CONF_HOST]}

            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: user_input[CONF_HOST],
                }
            )

            try:
                # Validate the ip address
                serial = await validate_host_input(user_input[CONF_HOST])
            except (ConnectionError, ClientConnectionError):
                errors["base"] = "cannot_connect"
                local_schema = vol.Schema(
                    {vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str}
                )
            else:
                await self.async_set_unique_id(serial)

                return self.async_create_entry(
                    title="Fireplace",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                    },
                )

        return self.async_show_form(
            step_id="local_config",
            errors=errors,
            description_placeholders=placeholder,
            data_schema=local_schema,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick which device to configure."""

        if user_input is not None:
            # Update not_configured_hosts in order to trigger correct
            # behavior in next step

            return await self.async_step_local_config(user_input=user_input)

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST): vol.In(self._not_configured_hosts)}
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the user flow."""

        # Launch fireplaces discovery
        await self._find_fireplaces()

        if len(self._not_configured_hosts) > 1:
            return await self.async_step_pick_device()
        return await self.async_step_local_config()
