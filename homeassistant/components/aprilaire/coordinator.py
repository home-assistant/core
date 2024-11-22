"""The Aprilaire coordinator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

import pyaprilaire.client
from pyaprilaire.const import MODELS, Attribute, FunctionalDomain

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import BaseDataUpdateCoordinatorProtocol

from .const import DOMAIN

RECONNECT_INTERVAL = 60 * 60
RETRY_CONNECTION_INTERVAL = 10
WAIT_TIMEOUT = 30

_LOGGER = logging.getLogger(__name__)

type AprilaireConfigEntry = ConfigEntry[AprilaireCoordinator]


class AprilaireCoordinator(BaseDataUpdateCoordinatorProtocol):
    """Coordinator for interacting with the thermostat."""

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str | None,
        host: str,
        port: int,
    ) -> None:
        """Initialize the coordinator."""

        self.hass = hass
        self.unique_id = unique_id
        self.data: dict[str, Any] = {}

        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}

        self.client = pyaprilaire.client.AprilaireClient(
            host,
            port,
            self.async_set_updated_data,
            _LOGGER,
            RECONNECT_INTERVAL,
            RETRY_CONNECTION_INTERVAL,
        )

        if hasattr(self.client, "data") and self.client.data:
            self.data = self.client.data

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)

        self._listeners[remove_listener] = (update_callback, context)

        return remove_listener

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()

    def async_set_updated_data(self, data: Any) -> None:
        """Manually update data, notify listeners and reset refresh interval."""

        old_device_info = self.create_device_info(self.data)

        self.data = self.data | data

        self.async_update_listeners()

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
                    device_id=device.id,
                    **new_device_info,  # type: ignore[misc]
                )

    async def start_listen(self):
        """Start listening for data."""
        await self.client.start_listen()

    def stop_listen(self):
        """Stop listening for data."""
        self.client.stop_listen()

    async def wait_for_ready(
        self, ready_callback: Callable[[bool], Awaitable[None]]
    ) -> bool:
        """Wait for the client to be ready."""

        if not self.data or Attribute.MAC_ADDRESS not in self.data:
            data = await self.client.wait_for_response(
                FunctionalDomain.IDENTIFICATION, 2, WAIT_TIMEOUT
            )

            if not data or Attribute.MAC_ADDRESS not in data:
                _LOGGER.error("Missing MAC address")
                await ready_callback(False)

                return False

        if not self.data or Attribute.NAME not in self.data:
            await self.client.wait_for_response(
                FunctionalDomain.IDENTIFICATION, 4, WAIT_TIMEOUT
            )

        if not self.data or Attribute.THERMOSTAT_MODES not in self.data:
            await self.client.wait_for_response(
                FunctionalDomain.CONTROL, 7, WAIT_TIMEOUT
            )

        if (
            not self.data
            or Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS not in self.data
        ):
            await self.client.wait_for_response(
                FunctionalDomain.SENSORS, 2, WAIT_TIMEOUT
            )

        await ready_callback(True)

        return True

    @property
    def device_name(self) -> str:
        """Get the name of the thermostat."""

        return self.create_device_name(self.data)

    def create_device_name(self, data: dict[str, Any] | None) -> str:
        """Create the name of the thermostat."""

        name = data.get(Attribute.NAME) if data else None

        return name if name else "Aprilaire"

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

        if data is None or Attribute.MAC_ADDRESS not in data or self.unique_id is None:
            return None

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.create_device_name(data),
            manufacturer="Aprilaire",
        )

        model_number = data.get(Attribute.MODEL_NUMBER)
        if model_number is not None:
            device_info["model"] = MODELS.get(model_number, f"Unknown ({model_number})")

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
