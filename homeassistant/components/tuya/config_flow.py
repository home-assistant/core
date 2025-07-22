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
            return await self.async_step_no_energy_devices()

        if user_input is not None:
            return self._process_device_configuration(user_input)

        return self._build_options_form()

    def _process_device_configuration(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Process device-specific settings and create config entry."""
        device_configs = {}

        # Convert user-friendly field keys back to device IDs
        for field_key, value in user_input.items():
            if field_key in self._device_field_mapping:
                device_id = self._device_field_mapping[field_key]
                device_configs[device_id] = value

        return self.async_create_entry(
            title="", data={"device_energy_modes": device_configs}
        )

    def _build_options_form(self) -> ConfigFlowResult:
        """Build the options form with device energy mode selectors."""
        schema_dict = {}
        current_options = self.config_entry.options.get("device_energy_modes", {})
        device_field_mapping = {}

        for device_id, device_display_name in self._energy_devices:
            field_key = self._create_device_field_key(device_display_name, device_id)
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

    def _create_device_field_key(self, device_display_name: str, device_id: str) -> str:
        """Create user-friendly field key from device display name and ID."""
        device_name = device_display_name
        sensor_info = ""
        if " &|& " in device_display_name:
            device_name, sensor_info = device_display_name.split(" &|& ", 1)

        return f"{device_name} [{device_id}] [{sensor_info}]"

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

        Returns:
            List of tuples: (device_id, device_display_name)
            Example: [("bf123456", "Energy Storage &|& battery_level, charging_power")]
        """
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        # Get all entities for this config entry
        entities = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        # Collect energy devices and their sensors
        energy_devices = self._collect_energy_devices(entities, device_registry)

        # Convert to display format
        return self._format_device_list(energy_devices)

    def _collect_energy_devices(
        self, entities: list[er.RegistryEntry], device_registry: dr.DeviceRegistry
    ) -> dict[str, dict[str, Any]]:
        """Collect energy devices and their associated sensors."""
        energy_devices: dict[str, dict[str, Any]] = {}

        for entity in entities:
            if not self._is_energy_sensor(entity) or entity.device_id is None:
                continue

            # Get device information and extract Tuya device ID
            ha_device = device_registry.async_get(entity.device_id)
            tuya_device_id = self._get_tuya_device_id(ha_device)
            if not tuya_device_id or ha_device is None:
                continue

            # Get device display name
            device_name = (
                ha_device.name_by_user or ha_device.name or f"Device {tuya_device_id}"
            )

            # Initialize device entry if not exists
            if tuya_device_id not in energy_devices:
                energy_devices[tuya_device_id] = {
                    "name": device_name,
                    "sensors": [],
                }

            # Add sensor to device
            sensor_name = entity.original_name or entity.name or "Unknown Sensor"
            energy_devices[tuya_device_id]["sensors"].append(sensor_name)

        return energy_devices

    def _is_energy_sensor(self, entity: er.RegistryEntry) -> bool:
        """Check if an entity is a valid energy sensor."""
        return (
            entity.domain == "sensor"
            and entity.platform == "tuya"
            and entity.original_device_class in ("energy", "energy_storage")
            and entity.device_id is not None
            and entity.capabilities is not None
            and entity.capabilities.get("state_class") in ("total_increasing", "total")
        )

    def _get_tuya_device_id(self, ha_device: dr.DeviceEntry | None) -> str | None:
        """Extract Tuya device ID from Home Assistant device identifiers."""
        if not ha_device or not ha_device.identifiers:
            return None

        return next(
            (
                identifier
                for domain, identifier in ha_device.identifiers
                if domain == "tuya"
            ),
            None,
        )

    def _format_device_list(
        self, energy_devices: dict[str, dict[str, Any]]
    ) -> list[tuple[str, str]]:
        """Convert internal dictionary to expected return format."""
        result = []
        for device_id, device_info in energy_devices.items():
            # Format sensor list for display
            sensors = device_info["sensors"]
            if not sensors:
                sensors_text = "No sensors"
            elif len(sensors) <= 3:
                sensors_text = ", ".join(sensors)
            else:
                sensors_text = f"{', '.join(sensors[:3])} (+{len(sensors) - 3} more)"

            # Create display name with separator
            device_display_name = f"{device_info['name']} &|& {sensors_text}"
            result.append((device_id, device_display_name))

        return result
