"""Config flow for Bluetti BT integration."""

import logging
from typing import Any, override

from bluetti_bt_lib import recognize_device
from habluetooth import BluetoothServiceInfoBleak
from probatio import Schema

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_API_VERSION, CONF_MODEL

from .const import CONF_ENCRYPTION, CONF_SERIAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BluettiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Bluetti BT devices."""

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""
        _LOGGER.debug("Discovered matching device")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_user()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user input."""

        errors: dict[str, str] = {}

        if not self._discovery_info:
            errors["base"] = "no_unconfigured_devices"
            return self.async_abort(reason="no_unconfigured_devices")

        # Handle discovery proceed setup
        if user_input is not None:
            await self.async_set_unique_id(
                self._discovery_info.address, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()

            data = await self._async_detect_bluetti_device(self._discovery_info.address)

            if data is None:
                errors["base"] = "unsupported_device"
                return self.async_abort(reason="unsupported_device")

            # Save entry
            return self.async_create_entry(
                title=str(data.get(CONF_MODEL)),
                data=data,
            )

        # We don't have manual configs, only via discovery
        return self.async_show_form(
            step_id="user",
            data_schema=Schema({}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguring."""

        if user_input is not None:
            entry = self._get_reconfigure_entry()
            address = str(entry.data.get(CONF_ADDRESS))

            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_mismatch()

            data = await self._async_detect_bluetti_device(address)

            if data is None:
                return self.async_abort(reason="unsupported_device")

            return self.async_update_reload_and_abort(
                entry,
                data_updates=data,
            )

        # We don't have manual configs, only via discovery
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=Schema({}),
        )

    async def _async_detect_bluetti_device(self, address: str) -> dict | None:
        _LOGGER.debug("Starting device detection")

        # Run model detection
        result = await recognize_device(address, self.hass.loop.create_future)

        _LOGGER.debug("Device detection complete")

        if result is None:
            _LOGGER.error("Unknown or unsupported device")
            return None

        data = {
            CONF_ADDRESS: address,
            CONF_MODEL: result.name,
            CONF_SERIAL: str(result.sn),
            CONF_API_VERSION: result.iot_version,
            CONF_ENCRYPTION: result.encrypted,
        }

        _LOGGER.debug(data)

        return data
