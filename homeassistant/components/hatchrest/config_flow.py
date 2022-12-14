"""Discovery config flow for Hatch Rest device."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_ADDRESS): str,
    }
)


class HatchRestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluetooth discovery config flow for Hatch Rest devices."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual setup."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=MANUAL_SCHEMA,
                errors=None,
            )

        address = user_input[CONF_ADDRESS]
        await self.async_set_unique_id(format_mac(address))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={CONF_ADDRESS: address},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        _LOGGER.debug("Discovered hatch device: %s", discovery_info)
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=discovery_info.name,
            data={CONF_ADDRESS: discovery_info.address},
        )
