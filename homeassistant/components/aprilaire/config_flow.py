"""Config flow for the Aprilaire integration."""

from __future__ import annotations

import logging
from typing import Any

from pyaprilaire.const import Attribute
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .coordinator import AprilaireCoordinator

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=7000): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


class AprilaireConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aprilaire."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        coordinator = AprilaireCoordinator(
            self.hass, None, user_input[CONF_HOST], user_input[CONF_PORT]
        )
        await coordinator.start_listen()

        async def ready_callback(ready: bool):
            if not ready:
                _LOGGER.error("Failed to wait for ready")

        try:
            ready = await coordinator.wait_for_ready(ready_callback)
        finally:
            coordinator.stop_listen()

        mac_address = coordinator.data.get(Attribute.MAC_ADDRESS)

        if ready and mac_address is not None:
            await self.async_set_unique_id(format_mac(mac_address))

            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Aprilaire", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors={"base": "connection_failed"},
        )
