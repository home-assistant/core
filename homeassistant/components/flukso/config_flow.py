"""Config flow for Flukso."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_DEVICE_HASH, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Flukso config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        pass

    async def _async_create_flukso(self, device_hash):
        unique_id = DOMAIN + "_" + device_hash

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        _LOGGER.info(f"Creating new entry for Flukso {device_hash}")

        return self.async_create_entry(
            title=f"Flukso {device_hash}", data={CONF_DEVICE_HASH: device_hash}
        )

    async def async_step_mqtt(self, discovery_info: DiscoveryInfoType) -> FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        splitted_topic = discovery_info["topic"].split("/")
        device_hash = splitted_topic[2]
        return await self._async_create_flukso(device_hash)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            device_hash = user_input[CONF_DEVICE_HASH]
            return await self._async_create_flukso(device_hash)

        fields = {}
        fields[vol.Required(CONF_DEVICE_HASH)] = str
        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields))
