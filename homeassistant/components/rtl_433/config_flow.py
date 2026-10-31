"""Config flow for the rtl_433 integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT

from .const import (
    CONF_SECURE,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DOMAIN,
    MINOR_VERSION,
    VERSION,
)
from .coordinator import CannotConnect, Rtl433Coordinator

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
        probatio.Required(CONF_PATH, default=DEFAULT_PATH): str,
        probatio.Optional(CONF_SECURE, default=False): bool,
    }
)


def _hub_unique_id(host: str, port: int) -> str:
    """Return the unique_id for a hub entry (one per host:port)."""
    return f"hub:{host}:{port}"


class Rtl433ConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle setup of an rtl_433 hub (one config entry per server)."""

    VERSION = VERSION
    MINOR_VERSION = MINOR_VERSION

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect hub connection params, validate, and create a hub entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]
            path: str = user_input[CONF_PATH]
            secure: bool = user_input[CONF_SECURE]

            await self.async_set_unique_id(_hub_unique_id(host, port))
            self._abort_if_unique_id_configured()

            try:
                await Rtl433Coordinator.validate_connection(
                    self.hass, host, port, path, secure=secure
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"rtl_433 ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PATH: path,
                        CONF_SECURE: secure,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
