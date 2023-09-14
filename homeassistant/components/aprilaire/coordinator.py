"""The Aprilaire coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from logging import Logger
from typing import Any

import pyaprilaire.client
from pyaprilaire.const import MODELS, Attribute, FunctionalDomain

from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

RECONNECT_INTERVAL = 60 * 60
RETRY_CONNECTION_INTERVAL = 10


class AprilaireCoordinator(DataUpdateCoordinator):
    """Coordinator for interacting with the thermostat."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, logger: Logger
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
        )

        self.data: dict[str, Any] = {}

        self.client = pyaprilaire.client.AprilaireClient(
            host,
            port,
            self.async_set_updated_data,
            self.logger,
            RECONNECT_INTERVAL,
            RETRY_CONNECTION_INTERVAL,
        )

    def async_set_updated_data(self, data: Any) -> None:
        """Manually update data, notify listeners and reset refresh interval."""

        old_device_info = self.create_device_info(self.data)

        if self.data is not None:
            data = self.data | data

        super().async_set_updated_data(data)

        new_device_info = self.create_device_info(data)

        if (
            old_device_info is not None
            and new_device_info is not None
            and old_device_info != new_device_info
        ):
            device_registry = dr.async_get(self.hass)

            device = device_registry.async_get_device(old_device_info["identifiers"])

            if device is not None:
                new_device_info.pop("identifiers", None)
                new_device_info.pop("connections", None)

                device_registry.async_update_device(
                    device_id=device.id, **new_device_info  # type: ignore[misc]
                )

    async def start_listen(self):
        """Start listening for data."""
        await self.client.start_listen()

    def stop_listen(self):
        """Stop listening for data."""
        self.client.stop_listen()

    async def wait_for_ready(
        self, ready_callback: Callable[[bool], Awaitable[bool]]
    ) -> bool:
        """Wait for the client to be ready."""

        if not self.data or Attribute.MAC_ADDRESS not in self.data:
            data = await self.client.wait_for_response(
                FunctionalDomain.IDENTIFICATION, 2, 30
            )

            if not data or Attribute.MAC_ADDRESS not in data:
                self.logger.error("Missing MAC address, cannot create unique ID")
                await ready_callback(False)

                return False

        if not self.data or Attribute.NAME not in self.data:
            await self.client.wait_for_response(FunctionalDomain.IDENTIFICATION, 4, 30)

        if not self.data or Attribute.THERMOSTAT_MODES not in self.data:
            await self.client.wait_for_response(FunctionalDomain.CONTROL, 7, 30)

        if (
            not self.data
            or Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS not in self.data
        ):
            await self.client.wait_for_response(FunctionalDomain.SENSORS, 2, 30)

        await ready_callback(True)

        return True

    @property
    def device_name(self) -> str:
        """Get the name of the thermostat."""

        return self.create_device_name(self.data)

    def create_device_name(self, data: dict[str, Any]) -> str:
        """Create the name of the thermostat."""

        name = data.get(Attribute.NAME)

        if name is None or len(name) == 0:
            return "Aprilaire"

        return name

    def get_hw_version(self, data: dict[str, Any]) -> str:
        """Get the hardware version."""

        if hardware_revision := data.get(Attribute.HARDWARE_REVISION):
            return (
                f"Rev. {chr(hardware_revision)}"
                if hardware_revision > ord("A")
                else str(hardware_revision)
            )

        return "Unknown"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get the device info for the thermostat."""
        return self.create_device_info(self.data)

    def create_device_info(self, data: dict[str, Any]) -> DeviceInfo | None:
        """Create the device info for the thermostat."""

        if Attribute.MAC_ADDRESS not in data:
            return None

        device_info = DeviceInfo(
            identifiers={(DOMAIN, data[Attribute.MAC_ADDRESS])},
            name=self.create_device_name(data),
            manufacturer="Aprilaire",
        )

        model_number = data.get(Attribute.MODEL_NUMBER)
        if model_number is not None:
            device_info["model"] = (
                MODELS[model_number]
                if model_number in MODELS
                else f"Unknown ({model_number})"
            )

        device_info["hw_version"] = self.get_hw_version(data)

        firmware_major_revision = data.get(Attribute.FIRMWARE_MAJOR_REVISION)
        firmware_minor_revision = data.get(Attribute.FIRMWARE_MINOR_REVISION)
        if firmware_major_revision is not None:
            device_info["sw_version"] = (
                str(firmware_major_revision)
                if firmware_minor_revision is None
                else f"{firmware_major_revision}.{firmware_minor_revision:02}"
            )

        return device_info
