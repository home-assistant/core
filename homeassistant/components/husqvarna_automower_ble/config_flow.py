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
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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


class HusqvarnaAutomowerBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Husqvarna Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.address: str
        self.pin: int | None

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

        if user_input is not None:
            self.pin = user_input[CONF_PIN]
            return await self.async_step_bluetooth_finalise()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PIN): int,
                },
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial manual step."""

        if user_input is not None:
            self.address = user_input[CONF_ADDRESS]
            self.pin = user_input[CONF_PIN]
            await self.async_set_unique_id(self.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_finalise()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Required(CONF_PIN): int,
                },
            ),
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
        ble_flow: bool,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Check that the mower exists and is setup."""
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

            if response_result is not ResponseResult.OK:
                if (
                    response_result is ResponseResult.INVALID_PIN
                    or response_result is ResponseResult.NOT_ALLOWED
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"

                if ble_flow:
                    return self.async_show_form(
                        step_id="bluetooth_confirm",
                        data_schema=vol.Schema(
                            {
                                vol.Required(CONF_PIN): int,
                            },
                        ),
                        errors=errors,
                    )
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_ADDRESS): str,
                            vol.Required(CONF_PIN): int,
                        },
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

    async def async_step_bluetooth_finalise(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Finalise the Bluetooth setup."""
        return await self.check_mower(True, user_input)

    async def async_step_finalise(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Finalise the Manual setup."""
        return await self.check_mower(False, user_input)

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

        if user_input:
            self.address = user_input[CONF_ADDRESS]
            self.pin = user_input[CONF_PIN]

            try:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                ) or await get_device(self.address)

                (channel_id, mower) = await self.connect_mower(device)

                response_result = await mower.connect(device)
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
                        CONF_PIN: self.pin,
                    }

                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=data
                    )

            except (TimeoutError, BleakError):
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Required(CONF_PIN): int,
                },
            ),
            errors=errors,
        )
