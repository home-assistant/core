"""Config flow for Hue BLE integration."""

from __future__ import annotations

import logging
from typing import Any

from HueBLE import HueBleLight
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.api import (
    async_ble_device_from_address,
    async_scanner_count,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, URL_PAIRING_MODE

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, address: str) -> None:
    """Validate that we can connect."""

    ble_device = async_ble_device_from_address(hass, address.upper(), connectable=True)

    if ble_device is None:
        count_scanners = async_scanner_count(hass, connectable=True)
        _LOGGER.debug("Count of BLE scanners in HA bt: %i", count_scanners)

        if count_scanners < 1:
            raise ScannerNotAvailable
        raise NotFound

    try:
        light = HueBleLight(ble_device)

        await light.connect()

        if light.authenticated is None:
            _LOGGER.warning(
                "Unable to determine if light authenticated, proceeding anyway"
            )
        elif not light.authenticated:
            raise InvalidAuth

        if not light.connected:
            raise CannotConnect

        state_changed, errors = await light.poll_state()
        if not len(errors) == 0:
            raise CannotConnect
    finally:
        await light.disconnect()


class HueBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hue BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the home assistant scanner."""

        _LOGGER.debug(
            "HA found light %s. Will show in UI but not auto connect",
            discovery_info.name,
        )

        unique_id = dr.format_mac(discovery_info.address)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        name = f"{discovery_info.name} ({discovery_info.address})"
        self.context.update({"title_placeholders": {CONF_NAME: name}})

        self._discovery_info = discovery_info

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single device."""

        assert self._discovery_info is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                unique_id = dr.format_mac(self._discovery_info.address)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                await validate_input(self.hass, unique_id)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ScannerNotAvailable:
                errors["base"] = "no_scanners"
            except NotFound:
                errors["base"] = "not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=self._discovery_info.name, data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                CONF_NAME: self._discovery_info.name,
                CONF_MAC: self._discovery_info.address,
                "url_pairing_mode": URL_PAIRING_MODE,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ScannerNotAvailable(HomeAssistantError):
    """Error to indicate no bluetooth scanners are available."""


class NotFound(HomeAssistantError):
    """Error to indicate the light could not be found."""
