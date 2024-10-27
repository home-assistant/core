"""Config flow for Motionblinds Bluetooth integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from bleak.backends.device import BLEDevice
from motionblindsble.const import DISPLAY_NAME, SETTING_DISCONNECT_TIME, MotionBlindType
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BLIND_TYPE,
    CONF_LOCAL_NAME,
    CONF_MAC_CODE,
    DOMAIN,
    ERROR_COULD_NOT_FIND_MOTOR,
    ERROR_INVALID_MAC_CODE,
    ERROR_NO_BLUETOOTH_ADAPTER,
    ERROR_NO_DEVICES_FOUND,
    OPTION_DISCONNECT_TIME,
    OPTION_PERMANENT_CONNECTION,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_MAC_CODE): str})


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Motionblinds Bluetooth."""

    def __init__(self) -> None:
        """Initialize a ConfigFlow."""
        self._discovery_info: BluetoothServiceInfoBleak | BLEDevice | None = None
        self._mac_code: str | None = None
        self._display_name: str | None = None
        self._blind_type: MotionBlindType | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug(
            "Discovered Motionblinds bluetooth device: %s", discovery_info.as_dict()
        )
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._mac_code = get_mac_from_local_name(discovery_info.name)
        self._display_name = display_name = DISPLAY_NAME.format(mac_code=self._mac_code)
        self.context["title_placeholders"] = {"name": display_name}

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mac_code = user_input[CONF_MAC_CODE]
            # Discover with BLE
            try:
                await self.async_discover_motionblind(mac_code)
            except NoBluetoothAdapter:
                return self.async_abort(reason=EXCEPTION_MAP[NoBluetoothAdapter])
            except NoDevicesFound:
                return self.async_abort(reason=EXCEPTION_MAP[NoDevicesFound])
            except tuple(EXCEPTION_MAP.keys()) as e:
                errors = {"base": EXCEPTION_MAP.get(type(e), str(type(e)))}
                return self.async_show_form(
                    step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
                )
            return await self.async_step_confirm()

        scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
        if not scanner_count:
            _LOGGER.error("No bluetooth adapter found")
            return self.async_abort(reason=EXCEPTION_MAP[NoBluetoothAdapter])

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single device."""
        if user_input is not None:
            self._blind_type = user_input[CONF_BLIND_TYPE]

            if TYPE_CHECKING:
                assert self._discovery_info is not None

            return self.async_create_entry(
                title=str(self._display_name),
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_LOCAL_NAME: self._discovery_info.name,
                    CONF_MAC_CODE: self._mac_code,
                    CONF_BLIND_TYPE: self._blind_type,
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BLIND_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                blind_type.name.lower()
                                for blind_type in MotionBlindType
                            ],
                            translation_key=CONF_BLIND_TYPE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"display_name": self._display_name},
        )

    async def async_discover_motionblind(self, mac_code: str) -> None:
        """Discover Motionblinds initialized by the user."""
        if not is_valid_mac(mac_code):
            _LOGGER.error("Invalid MAC code: %s", mac_code.upper())
            raise InvalidMACCode

        scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
        if not scanner_count:
            _LOGGER.error("No bluetooth adapter found")
            raise NoBluetoothAdapter

        bleak_scanner = bluetooth.async_get_scanner(self.hass)
        devices = await bleak_scanner.discover()

        if len(devices) == 0:
            _LOGGER.error("Could not find any bluetooth devices")
            raise NoDevicesFound

        motion_device: BLEDevice | None = next(
            (
                device
                for device in devices
                if device
                and device.name
                and f"MOTION_{mac_code.upper()}" in device.name
            ),
            None,
        )

        if motion_device is None:
            _LOGGER.error("Could not find a motor with MAC code: %s", mac_code.upper())
            raise CouldNotFindMotor

        await self.async_set_unique_id(motion_device.address, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        self._discovery_info = motion_device
        self._mac_code = mac_code.upper()
        self._display_name = DISPLAY_NAME.format(mac_code=self._mac_code)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Motionblinds BLE."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        OPTION_PERMANENT_CONNECTION,
                        default=(
                            self.config_entry.options.get(
                                OPTION_PERMANENT_CONNECTION, False
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        OPTION_DISCONNECT_TIME,
                        default=(
                            self.config_entry.options.get(
                                OPTION_DISCONNECT_TIME, SETTING_DISCONNECT_TIME
                            )
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                }
            ),
        )


def is_valid_mac(data: str) -> bool:
    """Validate the provided MAC address."""

    mac_regex = r"^[0-9A-Fa-f]{4}$"
    return bool(re.match(mac_regex, data))


def get_mac_from_local_name(data: str) -> str | None:
    """Get the MAC address from the bluetooth local name."""

    mac_regex = r"^MOTION_([0-9A-Fa-f]{4})$"
    match = re.search(mac_regex, data)
    return str(match.group(1)) if match else None


class CouldNotFindMotor(HomeAssistantError):
    """Error to indicate no motor with that MAC code could be found."""


class InvalidMACCode(HomeAssistantError):
    """Error to indicate the MAC code is invalid."""


class NoBluetoothAdapter(HomeAssistantError):
    """Error to indicate no bluetooth adapter could be found."""


class NoDevicesFound(HomeAssistantError):
    """Error to indicate no bluetooth devices could be found."""


EXCEPTION_MAP = {
    NoBluetoothAdapter: ERROR_NO_BLUETOOTH_ADAPTER,
    NoDevicesFound: ERROR_NO_DEVICES_FOUND,
    CouldNotFindMotor: ERROR_COULD_NOT_FIND_MOTOR,
    InvalidMACCode: ERROR_INVALID_MAC_CODE,
}
