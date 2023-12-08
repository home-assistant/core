"""Config flow for Decora BLE."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from decora_bleak import (
    DECORA_SERVICE_UUID,
    DecoraBLEDevice,
    DeviceConnectionError,
    DeviceNotInPairingModeError,
    IncorrectAPIKeyError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY, CONF_DEVICES, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN
from .models import DiscoveredDecoraDevice


class DecoraBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Decora BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._setting_up_device: DiscoveredDecoraDevice | None = None
        self._discovered_devices: dict[str, DiscoveredDecoraDevice] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._setting_up_device = DiscoveredDecoraDevice(
            name=discovery_info.name,
            address=discovery_info.address.upper(),
            api_key=None,
        )
        return await self.async_step_device_configuration()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            self._setting_up_device = self._discovered_devices[address]
            return await self.async_step_device_configuration()

        current_addresses = self._async_current_ids()
        for discovery in async_discovered_service_info(self.hass):
            address = discovery.address.upper()
            if (
                address in current_addresses
                or address in self._discovered_devices
                or DECORA_SERVICE_UUID not in discovery.service_uuids
            ):
                continue
            self._discovered_devices[address] = DiscoveredDecoraDevice(
                name=discovery.name, address=address, api_key=None
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        device.address: (f"{device.name} ({device.address})")
                        for device in self._discovered_devices.values()
                    }
                )
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import devices configured using the old configuration.yaml file method."""
        current_addresses = self._async_current_ids()
        at_least_one_device_needs_import = False

        for raw_address, device_config in config[CONF_DEVICES].items():
            address = raw_address.upper()
            if address not in current_addresses:
                device = DiscoveredDecoraDevice(
                    name=device_config[CONF_NAME],
                    address=address,
                    api_key=device_config[CONF_API_KEY],
                )
                self._discovered_devices[address] = device
                at_least_one_device_needs_import = True

        if at_least_one_device_needs_import:
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.4.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": "Decora",
                },
            )
            return await self.async_step_user()

        return self.async_abort(reason="already_configured")

    async def async_step_device_configuration(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a specific device the user has chosen to set up."""
        setting_up_device = self._setting_up_device
        assert setting_up_device is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            setting_up_device, error = await self._verify_device_connection(
                setting_up_device
            )
            self._setting_up_device = setting_up_device

            if setting_up_device.api_key is not None and error is None:
                await self.async_set_unique_id(setting_up_device.address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_ADDRESS: setting_up_device.address,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_API_KEY: setting_up_device.api_key,
                    },
                )

            if error is not None:
                if self.context["source"] == config_entries.SOURCE_IMPORT:
                    async_create_issue(
                        self.hass,
                        DOMAIN,
                        f"deprecated_yaml_import_issue_{error}",
                        breaks_in_ha_version="2024.4.0",
                        is_fixable=True,
                        is_persistent=False,
                        issue_domain=DOMAIN,
                        severity=IssueSeverity.WARNING,
                        translation_key="deprecated_yaml",
                        translation_placeholders={
                            "domain": DOMAIN,
                            "integration_title": "Decora",
                        },
                    )
                errors["base"] = error

        placeholders = {"name": setting_up_device.name}
        self.context["title_placeholders"] = placeholders

        field_values = (
            user_input
            if user_input is not None
            else {CONF_NAME: setting_up_device.name}
        )
        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=field_values.get(CONF_NAME)): str,
            }
        )

        return self.async_show_form(
            step_id="device_configuration",
            description_placeholders=placeholders,
            data_schema=data_schema,
            errors=errors,
        )

    async def _verify_device_connection(
        self, device: DiscoveredDecoraDevice
    ) -> tuple[DiscoveredDecoraDevice, Optional[str]]:
        if device.api_key is not None:
            return await self._verify_api_key(device)

        return await self._get_api_key(device)

    async def _verify_api_key(
        self, device: DiscoveredDecoraDevice
    ) -> tuple[DiscoveredDecoraDevice, Optional[str]]:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, device.address, connectable=True
        )

        if not ble_device:
            return device, "cannot_connect"

        try:
            decora_ble_device = DecoraBLEDevice(ble_device, device.api_key)
            await decora_ble_device.connect()
            return device, None
        except IncorrectAPIKeyError:
            device = replace(device, api_key=None)
            return device, "incorrect_api_key"
        except DeviceConnectionError:
            return device, "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            return device, "unknown_error"

    async def _get_api_key(
        self, device: DiscoveredDecoraDevice
    ) -> tuple[DiscoveredDecoraDevice, Optional[str]]:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, device.address, connectable=True
        )

        if not ble_device:
            return device, "cannot_connect"

        try:
            api_key = await DecoraBLEDevice.get_api_key(ble_device)
            device = replace(device, api_key=api_key)
            return device, None
        except DeviceNotInPairingModeError:
            return device, "not_in_pairing_mode"
        except DeviceConnectionError:
            return device, "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            return device, "unknown_error"
