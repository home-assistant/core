"""Config flow to configure DSMR Reader."""
from __future__ import annotations

from collections.abc import Awaitable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(_: HomeAssistant) -> bool:
    """Return true as this integration doesn't support any real devices."""
    return True


class DsmrReaderFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Handle DSMR Reader config flow. The MQTT step is inherited from the parent class."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the config flow."""
        super().__init__(DOMAIN, "DSMR Reader", _async_has_devices)

    async def async_step_import(self, _: dict[str, Any] | None) -> FlowResult:
        """Import from configuration.yaml and create config entry."""
        if not self.hass.services.has_service(domain="mqtt", service="publish"):
            _LOGGER.warning("DSMR Reader configuration import failed. MQTT is missing")
            return self.async_abort(reason="mqtt_missing")

        return await super().async_step_import(None)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step."""
        if not self.hass.services.has_service(domain="mqtt", service="publish"):
            return self.async_abort(reason="mqtt_missing")

        return await super().async_step_user(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    "documentation_link": "https://www.home-assistant.io/integrations/dsmr_reader#setup"
                },
            )

        return await super().async_step_confirm(user_input)
