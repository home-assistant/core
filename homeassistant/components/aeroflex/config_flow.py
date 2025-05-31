"""Config flow for the Aeroflex Adjustable Bed integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AeroflexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aeroflex."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._selected_device_address: str | None = None
        self._selected_device_name: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self._selected_device_address = discovery_info.address
        self._selected_device_name = (
            discovery_info.name or f"Aeroflex Bed {discovery_info.address}"
        )
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        suggested_name = str(self._selected_device_name or "Aeroflex Bed")
        placeholders: Mapping[str, str] = {"name": suggested_name}

        if user_input is not None:
            device_name = user_input.get(CONF_NAME, suggested_name)
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_DEVICE_ADDRESS: discovery_info.address,
                    CONF_DEVICE_NAME: device_name,
                },
            )

        self._set_confirm_only()
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=suggested_name): str,
                }
            ),
        )
