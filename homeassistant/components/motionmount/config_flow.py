"""Config flow for Vogel's MotionMount."""
import motionmount

from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)

from .const import DOMAIN

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

class MotionMountFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Vogel's MotionMount config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the instance."""
        self.discovery_info: dict[str, Any] = {}

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.hostname

        # Avoid probing devices that already have an entry
        self._async_abort_entries_match({CONF_HOST: host})

        # Extract information from discovery
        port = discovery_info.port
        zctype = discovery_info.type
        name = discovery_info.name.replace(f".{zctype}", "")

        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
            }
        )

        await self._async_set_unique_id_and_abort_if_already_configured(host)

        self.context.update({"title_placeholders": {"name": name}})

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self.discovery_info[CONF_NAME]},
                errors={},
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )

    async def _async_set_unique_id_and_abort_if_already_configured(
        self, unique_id: str
    ) -> None:
        """Set the unique ID and abort if already configured."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
