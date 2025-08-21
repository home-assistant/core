"""Config flow for Husqvarna Bluetooth integration."""

from __future__ import annotations

from collections.abc import Mapping
import random
from typing import Any

from automower_ble.mower import Mower
from automower_ble.protocol import ResponseResult
from bleak import BleakError
from bleak_retry_connector import get_device
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import SOURCE_BLUETOOTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN

from .const import DOMAIN, LOGGER


def _is_supported(discovery_info: BluetoothServiceInfo):
    """Check if device is supported."""

    LOGGER.debug(
        "%s manufacturer data: %s",
        discovery_info.address,
        discovery_info.manufacturer_data,
    )

    manufacturer = any(key == 1062 for key in discovery_info.manufacturer_data)
    service_husqvarna = any(
        service == "98bd0001-0b0e-421a-84e5-ddbf75dc6de4"
        for service in discovery_info.service_uuids
    )
    service_generic = any(
        service == "00001800-0000-1000-8000-00805f9b34fb"
        for service in discovery_info.service_uuids
    )

    return manufacturer and service_husqvarna and service_generic


def _pin_valid(pin: str) -> bool:
    """Check if the pin is valid."""
    try:
        int(pin)
    except (TypeError, ValueError):
        return False
    return True


class HusqvarnaAutomowerBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Husqvarna Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.address: str | None = None
        self.pin: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""

        LOGGER.debug("Discovered device: %s", discovery_info)
        if not _is_supported(discovery_info):
            return self.async_abort(reason="no_devices_found")

        self.address = discovery_info.address
        await self.async_set_unique_id(self.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not _pin_valid(user_input[CONF_PIN]):
                errors["base"] = "invalid_pin"
            else:
                self.pin = user_input[CONF_PIN]
                return await self.check_mower(user_input)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_PIN): str,
                    },
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial manual step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not _pin_valid(user_input[CONF_PIN]):
                errors["base"] = "invalid_pin"
            else:
                self.address = user_input[CONF_ADDRESS]
                self.pin = user_input[CONF_PIN]
                await self.async_set_unique_id(self.address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return await self.check_mower(user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): str,
                        vol.Required(CONF_PIN): str,
                    },
                ),
                user_input,
            ),
            errors=errors,
        )

    async def probe_mower(self, device) -> str | None:
        """Probe the mower to see if it exists."""
        channel_id = random.randint(1, 0xFFFFFFFF)

        assert self.address

        try:
            (manufacturer, device_type, model) = await Mower(
                channel_id, self.address
            ).probe_gatts(device)
        except (BleakError, TimeoutError) as exception:
            LOGGER.exception(f"Failed to probe device ({self.address}): {exception}")
            return None

        title = manufacturer + " " + device_type

        LOGGER.debug("Found device: %s", title)

        return title

    async def connect_mower(self, device) -> tuple[int, Mower]:
        """Connect to the Mower."""
        assert self.address
        assert self.pin is not None

        channel_id = random.randint(1, 0xFFFFFFFF)
        mower = Mower(channel_id, self.address, self.pin)

        return (channel_id, mower)

    async def check_mower(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Check that the mower exists and is setup."""
        assert self.address

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

        title = await self.probe_mower(device)
        if title is None:
            return self.async_abort(reason="cannot_connect")

        try:
            errors: dict[str, str] = {}

            (channel_id, mower) = await self.connect_mower(device)

            response_result = await mower.connect(device)
            await mower.disconnect()

            if response_result is not ResponseResult.OK:
                LOGGER.debug("cannot connect, response: {response_result}")

                if (
                    response_result is ResponseResult.INVALID_PIN
                    or response_result is ResponseResult.NOT_ALLOWED
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

                if self.source == SOURCE_BLUETOOTH:
                    return self.async_show_form(
                        step_id="bluetooth_confirm",
                        data_schema=vol.Schema(
                            {
                                vol.Required(CONF_PIN): str,
                            },
                        ),
                        errors=errors,
                    )

                suggested_values = {}

                if self.address:
                    suggested_values[CONF_ADDRESS] = self.address
                if self.pin:
                    suggested_values[CONF_PIN] = self.pin

                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(
                            {
                                vol.Required(CONF_ADDRESS): str,
                                vol.Required(CONF_PIN): str,
                            },
                        ),
                        suggested_values,
                    ),
                    errors=errors,
                )
        except (TimeoutError, BleakError):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=title,
            data={
                CONF_ADDRESS: self.address,
                CONF_CLIENT_ID: channel_id,
                CONF_PIN: self.pin,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        if user_input is not None and not _pin_valid(user_input[CONF_PIN]):
            errors["base"] = "invalid_pin"
        elif user_input is not None:
            reauth_entry = self._get_reauth_entry()
            self.address = reauth_entry.data[CONF_ADDRESS]
            self.pin = user_input[CONF_PIN]

            try:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                ) or await get_device(self.address)

                (channel_id, mower) = await self.connect_mower(device)

                response_result = await mower.connect(device)
                await mower.disconnect()
                if (
                    response_result is ResponseResult.INVALID_PIN
                    or response_result is ResponseResult.NOT_ALLOWED
                ):
                    errors["base"] = "invalid_auth"
                elif response_result is not ResponseResult.OK:
                    errors["base"] = "cannot_connect"
                else:
                    data = {
                        CONF_ADDRESS: self.address,
                        CONF_CLIENT_ID: channel_id,
                        CONF_PIN: self.pin,
                    }

                    return self.async_update_reload_and_abort(reauth_entry, data=data)

            except (TimeoutError, BleakError):
                return self.async_abort(reason="cannot_connect")

        user_input = {}

        if self.pin:
            user_input[CONF_PIN] = self.pin

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_PIN): str,
                    },
                ),
                user_input,
            ),
            errors=errors,
        )
