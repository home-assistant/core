"""Config flow for Minecraft Server integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_TYPE

from .api import MinecraftServer, MinecraftServerAddressError, MinecraftServerType
from .const import DOMAIN

DEFAULT_ADDRESS = "localhost:25565"

_LOGGER = logging.getLogger(__name__)


class MinecraftServerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minecraft Server."""

    VERSION = 3

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate_input(user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_ADDRESS],
                    data={
                        CONF_ADDRESS: user_input[CONF_ADDRESS],
                        CONF_TYPE: user_input[CONF_TYPE],
                    },
                )

        return self._show_config_form(user_input, errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow for Minecraft Server."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate_input(user_input)

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    title=user_input[CONF_ADDRESS],
                    data_updates={
                        CONF_ADDRESS: user_input[CONF_ADDRESS],
                        CONF_TYPE: user_input[CONF_TYPE],
                    },
                )

        return self._show_config_form(
            user_input,
            errors,
            step_id="reconfigure",
            defaults=entry.data,
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate user input."""
        errors: dict[str, str] = {}
        server_type = MinecraftServerType(user_input[CONF_TYPE])
        server_address = user_input[CONF_ADDRESS]

        self._async_abort_entries_match({CONF_ADDRESS: server_address})
        api = MinecraftServer(self.hass, server_type, server_address)

        try:
            await api.async_initialize()
        except MinecraftServerAddressError as error:
            _LOGGER.debug(
                "Initialization of %s server failed: %s",
                server_type,
                error,
            )

            errors["base"] = "cannot_connect"
        else:
            if not await api.async_is_online():
                errors["base"] = "cannot_connect"

        return errors

    def _show_config_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        *,
        step_id: str = "user",
        defaults: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the configuration form to the user."""
        if user_input is None:
            user_input = {}
        if defaults is None:
            defaults = {}

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_TYPE,
                        default=user_input.get(
                            CONF_TYPE,
                            defaults.get(CONF_TYPE, MinecraftServerType.JAVA_EDITION),
                        ),
                    ): probatio.In(list(MinecraftServerType)),
                    probatio.Required(
                        CONF_ADDRESS,
                        default=user_input.get(
                            CONF_ADDRESS, defaults.get(CONF_ADDRESS, DEFAULT_ADDRESS)
                        ),
                    ): probatio.All(str, probatio.Lower),
                }
            ),
            errors=errors,
        )
