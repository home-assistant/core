"""Config flow for Tuya."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tuya_sharing import LoginControl
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector

from . import TuyaConfigEntry
from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    ENERGY_REPORT_MODE_CUMULATIVE,
    ENERGY_REPORT_MODE_INCREMENTAL,
    TUYA_CLIENT_ID,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_QR_CODE,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SCHEMA,
)


class TuyaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step scan."""
        if user_input is None:
            return self.async_show_form(
                step_id="scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
            )

        ret, info = await self.hass.async_add_executor_job(
            self.__login_control.login_result,
            self.__qr_code,
            TUYA_CLIENT_ID,
            self.__user_code,
        )
        if not ret:
            # Try to get a new QR code on failure
            await self.__async_get_qr_code(self.__user_code)
            return self.async_show_form(
                step_id="scan",
                errors={"base": "login_error"},
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
                description_placeholders={
                    TUYA_RESPONSE_MSG: info.get(TUYA_RESPONSE_MSG, "Unknown error"),
                    TUYA_RESPONSE_CODE: info.get(TUYA_RESPONSE_CODE, 0),
                },
            )

        entry_data = {
            CONF_USER_CODE: self.__user_code,
            CONF_TOKEN_INFO: {
                "t": info["t"],
                "uid": info["uid"],
                "expire_time": info["expire_time"],
                "access_token": info["access_token"],
                "refresh_token": info["refresh_token"],
            },
            CONF_TERMINAL_ID: info[CONF_TERMINAL_ID],
            CONF_ENDPOINT: info[CONF_ENDPOINT],
        }

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=entry_data,
            )

        return self.async_create_entry(
            title=info.get("username"),
            data=entry_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tuya."""
        if CONF_USER_CODE in entry_data:
            success, _ = await self.__async_get_qr_code(entry_data[CONF_USER_CODE])
            if success:
                return await self.async_step_scan()

        return await self.async_step_reauth_user_code()

    async def async_step_reauth_user_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a Tuya."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="reauth_user_code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def __async_get_qr_code(self, user_code: str) -> tuple[bool, dict[str, Any]]:
        """Get the QR code."""
        response = await self.hass.async_add_executor_job(
            self.__login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )
        if success := response.get(TUYA_RESPONSE_SUCCESS, False):
            self.__user_code = user_code
            self.__qr_code = response[TUYA_RESPONSE_RESULT][TUYA_RESPONSE_QR_CODE]
        return success, response

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TuyaConfigEntry) -> TuyaOptionsFlow:
        """Get the options flow for this handler."""
        return TuyaOptionsFlow()


class TuyaOptionsFlow(OptionsFlow):
    """Handle Tuya options."""

    def __init__(self) -> None:
        """Initialize Tuya options flow."""
        self._energy_devices: list[tuple[str, str]] = []  # (device_id, device_name)
        self._device_field_mapping: dict[str, str] = {}  # field_key -> device_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        # Get all energy devices
        self._energy_devices = await self._get_energy_devices()

        if not self._energy_devices:
            # No energy devices found, show a message instead of directly creating entry
            return self.async_show_form(
                step_id="no_energy_devices",
                data_schema=vol.Schema({}),
                description_placeholders={},
            )

        if user_input is not None:
            # Process device-specific settings using device IDs as keys
            device_configs = {}

            # Convert user-friendly field keys back to device IDs
            for field_key, value in user_input.items():
                if field_key in self._device_field_mapping:
                    device_id = self._device_field_mapping[field_key]
                    device_configs[device_id] = value

            return self.async_create_entry(
                title="", data={"device_energy_modes": device_configs}
            )

        # Build dynamic schema for each energy device
        schema_dict = {}
        current_options = self.config_entry.options.get("device_energy_modes", {})

        # Create one selector per device using device_id as key
        # We'll use a mapping to store the device display information
        device_field_mapping = {}

        for device_id, device_display_name in self._energy_devices:
            # Extract clean device name for display
            # Use the unique separator " &|& " to split device name and sensor info
            device_name = device_display_name
            sensor_info = ""
            if " &|& " in device_display_name:
                device_name = device_display_name.split(" &|& ")[0]
                sensor_info = device_display_name.split(" &|& ")[1]

            # Create field key that's user-friendly but still maps to device_id
            field_key = f"{device_name} [{device_id}] [{sensor_info}]"
            device_field_mapping[field_key] = device_id

            schema_dict[
                vol.Optional(
                    field_key,
                    default=current_options.get(
                        device_id, ENERGY_REPORT_MODE_CUMULATIVE
                    ),
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        ENERGY_REPORT_MODE_CUMULATIVE,
                        ENERGY_REPORT_MODE_INCREMENTAL,
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="energy_report_mode",
                )
            )

        # Store the mapping for use in processing
        self._device_field_mapping = device_field_mapping

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={},
        )

    async def async_step_no_energy_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the case when no energy devices are found."""
        if user_input is not None:
            # User acknowledged the message, create empty options entry
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="no_energy_devices",
            data_schema=vol.Schema({}),
            description_placeholders={},
        )

    async def _get_energy_devices(self) -> list[tuple[str, str]]:
        """Get all energy devices with their IDs and names, including sensor details.

        Scans all entities associated with this config entry to find energy sensors,
        groups them by device, and returns a list of tuples containing device ID
        and display name with sensor information.

        Returns:
            List of tuples: (device_id, device_display_name)
            Example: [("bf123456", "Energy Storage (battery_level, charging_power)")]

        """
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        # Get all entities for this config entry
        entities = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        # Track energy devices and their associated sensors
        # Structure: {device_id: {name: device_name, sensors: [sensor_names]}}
        energy_devices: dict[str, dict[str, Any]] = {}

        for entity in entities:
            # Skip entities that don't meet energy sensor criteria
            if (
                entity.domain != "sensor"
                or entity.platform != "tuya"
                or entity.original_device_class not in ("energy", "energy_storage")
                or not entity.device_id
                or not entity.capabilities
                or entity.capabilities.get("state_class", False)
                not in ("total_increasing", "total")
            ):
                continue

            # Get device information from Home Assistant device registry
            ha_device = device_registry.async_get(entity.device_id)
            if not ha_device or not ha_device.identifiers:
                continue

            # Extract Tuya device ID from device identifiers using modern Python
            tuya_device_id = next(
                (
                    identifier
                    for domain, identifier in ha_device.identifiers
                    if domain == "tuya"
                ),
                None,
            )
            if not tuya_device_id:
                continue

            # Get user-friendly device name, prioritizing user-defined names
            device_name = (
                ha_device.name_by_user or ha_device.name or f"Device {tuya_device_id}"
            )

            # Initialize device entry in tracking dictionary if not exists
            if tuya_device_id not in energy_devices:
                energy_devices[tuya_device_id] = {
                    "name": device_name,
                    "sensors": [],
                }
            sensor_name = entity.original_name or entity.name or "Unknown Sensor"
            energy_devices[tuya_device_id]["sensors"].append(sensor_name)

        # Convert internal dictionary to expected return format
        result = []
        for device_id, device_info in energy_devices.items():
            # Build sensor list display text, limiting to first 3 sensors
            sensors = device_info["sensors"]
            match len(sensors):
                case 0:
                    sensors_text = "No sensors"
                case n if n <= 3:
                    sensors_text = ", ".join(sensors)
                case n:
                    sensors_text = f"{', '.join(sensors[:3])} (+{n - 3} more)"

            # Create comprehensive display name using a unique separator
            # Use " &|& " as separator to avoid conflicts with device names and sensor info
            # This ASCII character combination is extremely unlikely to appear in device names
            device_display_name = f"{device_info['name']} &|& {sensors_text}"
            result.append((device_id, device_display_name))

        return result
