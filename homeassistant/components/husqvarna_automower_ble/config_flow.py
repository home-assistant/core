"""Config flow for Husqvarna Bluetooth integration."""

from __future__ import annotations

from collections.abc import Mapping
import random
from typing import Any

from automower_ble.mower import Mower
from automower_ble.protocol import ResponseResult
from bleak import BleakError
from bleak_retry_connector import get_device
from gardena_bluetooth.const import ScanService
from gardena_bluetooth.parse import ManufacturerData, ProductType
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import SOURCE_BLUETOOTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID, CONF_PIN

from .const import DOMAIN, LOGGER

BLUETOOTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PIN): str,
    }
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_PIN): str,
    }
)

REAUTH_SCHEMA = BLUETOOTH_SCHEMA


def _is_supported(discovery_info: BluetoothServiceInfo):
    """Check if device is supported."""
    if ScanService not in discovery_info.service_uuids:
        LOGGER.debug(
            "Unsupported device, missing service %s: %s", ScanService, discovery_info
        )
        return False

    if not (data := discovery_info.manufacturer_data.get(ManufacturerData.company)):
        LOGGER.debug(
            "Unsupported device, missing manufacturer data %s: %s",
            ManufacturerData.company,
            discovery_info,
        )
        return False

    manufacturer_data = ManufacturerData.decode(data)
    product_type = ProductType.from_manufacturer_data(manufacturer_data)

    # Some mowers only expose the serial number in the manufacturer data
    # and not the product type, so we allow None here as well.
    if product_type not in (ProductType.MOWER, None):
        LOGGER.debug("Unsupported device: %s (%s)", manufacturer_data, discovery_info)
        return False

    LOGGER.debug("Supported device: %s", manufacturer_data)
    return True


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

    address: str | None = None
    mower_name: str = ""
    pin: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""

        LOGGER.debug("Discovered device: %s", discovery_info)
        if not _is_supported(discovery_info):
            return self.async_abort(reason="no_devices_found")

        self.context["title_placeholders"] = {
            "name": discovery_info.name,
            "address": discovery_info.address,
        }
        self.address = discovery_info.address
        await self.async_set_unique_id(self.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        assert self.address
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
                BLUETOOTH_SCHEMA, user_input
            ),
            description_placeholders={"name": self.mower_name or self.address},
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
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def probe_mower(self, device) -> str | None:
        """Probe the mower to see if it exists."""
        channel_id = random.randint(1, 0xFFFFFFFF)

        assert self.address

        try:
            (manufacturer, device_type, _model) = await Mower(
                channel_id, self.address
            ).probe_gatts(device)
        except (BleakError, TimeoutError) as exception:
            LOGGER.exception("Failed to probe device (%s): %s", self.address, exception)
            return None

        title = manufacturer + " " + device_type

        LOGGER.debug("Found device: %s", title)

        return title

    async def connect_mower(self, device) -> tuple[int, Mower]:
        """Connect to the Mower."""
        assert self.address
        assert self.pin is not None

        channel_id = random.randint(1, 0xFFFFFFFF)
        mower = Mower(channel_id, self.address, int(self.pin))

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
            if self.source == SOURCE_BLUETOOTH:
                return self.async_show_form(
                    step_id="bluetooth_confirm",
                    data_schema=BLUETOOTH_SCHEMA,
                    description_placeholders={"name": self.address},
                    errors={"base": "cannot_connect"},
                )
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    USER_SCHEMA,
                    {
                        CONF_ADDRESS: self.address,
                        CONF_PIN: self.pin,
                    },
                ),
                errors={"base": "cannot_connect"},
            )
        self.mower_name = title

        try:
            errors: dict[str, str] = {}

            (channel_id, mower) = await self.connect_mower(device)

            response_result = await mower.connect(device)
            await mower.disconnect()

            if response_result is not ResponseResult.OK:
                LOGGER.debug("cannot connect, response: %s", response_result)

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
                        data_schema=BLUETOOTH_SCHEMA,
                        description_placeholders={
                            "name": self.mower_name or self.address
                        },
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
                        USER_SCHEMA, suggested_values
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
        reauth_entry = self._get_reauth_entry()
        self.address = reauth_entry.data[CONF_ADDRESS]
        self.mower_name = reauth_entry.title
        self.pin = reauth_entry.data.get(CONF_PIN, "")

        self.context["title_placeholders"] = {
            "name": self.mower_name,
            "address": self.address,
        }
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
            self.pin = user_input[CONF_PIN]

            try:
                assert self.address
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.address, connectable=True
                ) or await get_device(self.address)

                mower = Mower(
                    reauth_entry.data[CONF_CLIENT_ID], self.address, int(self.pin)
                )

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
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data=reauth_entry.data | {CONF_PIN: self.pin},
                    )

            except (TimeoutError, BleakError):
                # We don't want to abort a reauth flow when we can't connect, so
                # we just show the form again with an error.
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_PIN: self.pin}
            ),
            description_placeholders={"name": self.mower_name},
            errors=errors,
        )
