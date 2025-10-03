"""Config flow for Airthings BlE integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from airthings_ble import (
    AirthingsBluetoothDeviceData,
    AirthingsDevice,
    UnsupportedDeviceError,
)
from bleak import BleakError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, MFCT_ID

_LOGGER = logging.getLogger(__name__)

SERVICE_UUIDS = [
    "b42e1f6e-ade7-11e4-89d3-123b93f75cba",
    "b42e4a8e-ade7-11e4-89d3-123b93f75cba",
    "b42e1c08-ade7-11e4-89d3-123b93f75cba",
    "b42e3882-ade7-11e4-89d3-123b93f75cba",
    "b42e90a2-ade7-11e4-89d3-123b93f75cba",
]


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    name: str
    discovery_info: BluetoothServiceInfo
    device: AirthingsDevice
    data: AirthingsBluetoothDeviceData


def get_name(device: AirthingsDevice) -> str:
    """Generate name with model and identifier for device."""

    name = device.friendly_name()
    if identifier := device.identifier:
        name += f" ({device.model.value}{identifier})"
    return name


class AirthingsDeviceUpdateError(Exception):
    """Custom error class for device updates."""


class AirthingsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airthings BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: Discovery | None = None
        self._discovered_devices: dict[str, Discovery] = {}

    async def _get_device(
        self, data: AirthingsBluetoothDeviceData, discovery_info: BluetoothServiceInfo
    ) -> AirthingsDevice:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )
        if ble_device is None:
            _LOGGER.debug("no ble_device in _get_device_data")
            raise AirthingsDeviceUpdateError("No ble_device")

        try:
            device = await data.update_device(ble_device)
        except BleakError as err:
            raise AirthingsDeviceUpdateError("Failed getting device data") from err
        except UnsupportedDeviceError:
            _LOGGER.debug("Skipping unsupported device: %s", discovery_info.name)
            raise
        except Exception as err:
            _LOGGER.error(
                "Unknown error occurred from %s: %s", discovery_info.address, err
            )
            raise
        return device

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        data = AirthingsBluetoothDeviceData(logger=_LOGGER)

        try:
            device = await self._get_device(data=data, discovery_info=discovery_info)
        except AirthingsDeviceUpdateError:
            return self.async_abort(reason="cannot_connect")
        except UnsupportedDeviceError:
            return self.async_abort(reason="unsupported_device")
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="unknown")

        name = get_name(device)
        self.context["title_placeholders"] = {
            "name": name,
        }
        self._discovered_device = Discovery(name, discovery_info, device, data=data)

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None:
            if (
                self._discovered_device is not None
                and self._discovered_device.device.firmware.need_firmware_upgrade
            ):
                return self.async_abort(reason="firmware_upgrade_required")

            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"], data={}
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
            last_step=True,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            if discovery.device.firmware.need_firmware_upgrade:
                return self.async_abort(reason="firmware_upgrade_required")

            name = get_name(discovery.device)
            self.context["title_placeholders"] = {
                "name": name,
            }

            self._discovered_device = discovery

            return self.async_create_entry(title=name, data={})

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in list(async_discovered_service_info(self.hass)):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue

            if MFCT_ID not in discovery_info.manufacturer_data:
                continue

            if not any(uuid in SERVICE_UUIDS for uuid in discovery_info.service_uuids):
                _LOGGER.debug(
                    "Skipping unsupported device: %s (%s)", discovery_info.name, address
                )
                continue

            data = AirthingsBluetoothDeviceData(logger=_LOGGER)

            try:
                device = await self._get_device(data, discovery_info)
            except AirthingsDeviceUpdateError:
                _LOGGER.error(
                    "Error connecting to and getting data from %s",
                    discovery_info.address,
                )
                continue
            except UnsupportedDeviceError:
                continue
            except Exception:  # noqa: BLE001
                return self.async_abort(reason="unknown")

            name = get_name(device)
            _LOGGER.debug("Discovered Airthings device: %s (%s)", name, address)
            self._discovered_devices[address] = Discovery(
                name, discovery_info, device, data
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: get_name(discovery.device)
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(titles),
                },
            ),
        )
