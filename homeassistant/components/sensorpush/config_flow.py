"""Config flow for sensorpush integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .parser import parse_sensorpush_from_discovery_data

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for sensorpush."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: bluetooth.BluetoothServiceInfo | None = None
        self._discovered_device: dict[str, Any] | None = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("sensorpush discovery info: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not (
            device := parse_sensorpush_from_discovery_data(
                discovery_info.name, discovery_info.manufacturer_data
            )
        ):
            _LOGGER.debug(
                "sensorpush discovery info: %s is not a sensorpush device",
                discovery_info,
            )
            return self.async_abort(reason="not_sensorpush")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        if user_input is not None:
            return self.async_create_entry(title=device["type"], data={})

        self._set_confirm_only()
        placeholders = {"model": device["type"], "address": discovery_info.address}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )
