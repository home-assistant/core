"""Config flow for Home Assistant Supervisor integration."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import HASSIO_USER_NAME

from .const import (
    DATA_HASSIO_SUPERVISOR_USER,
    DEFAULT_UPDATE_OPTIONS,
    DOMAIN,
    ENTRY_DATA_USER,
)


class HassIoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Supervisor."""

    VERSION = 1

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data: dict[str, Any] = {}
        if (user := self.hass.data.get(DATA_HASSIO_SUPERVISOR_USER)) is not None:
            data[ENTRY_DATA_USER] = user.id

        return self.async_create_entry(
            title=HASSIO_USER_NAME,
            data=data,
            options=DEFAULT_UPDATE_OPTIONS,
        )
