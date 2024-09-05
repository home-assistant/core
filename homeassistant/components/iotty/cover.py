"""Implement a iotty Shutter Device."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from iottycloud.device import Device
from iottycloud.shutter import Shutter, ShutterState
from iottycloud.verbs import SH_DEVICE_TYPE_UID

from homeassistant.components.cover import CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IottyConfigEntry
from .api import IottyProxy
from .const import DOMAIN
from .coordinator import IottyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IottyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Activate the iotty Shutter component."""
    _LOGGER.debug("Setup COVER entry id is %s", config_entry.entry_id)

    coordinator = config_entry.runtime_data.coordinator
    entities = [
        IottyShutter(
            coordinator=coordinator, iotty_cloud=coordinator.iotty, iotty_device=d
        )
        for d in coordinator.data.devices
        if d.device_type == SH_DEVICE_TYPE_UID
        if (isinstance(d, Shutter))
    ]
    _LOGGER.debug("Found %d Shutters", len(entities))

    async_add_entities(entities)

    known_devices: set = config_entry.runtime_data.known_devices
    for known_device in coordinator.data.devices:
        if known_device.device_type == SH_DEVICE_TYPE_UID:
            known_devices.add(known_device)

    @callback
    def async_update_data() -> None:
        """Handle updated data from the API endpoint."""
        if not coordinator.last_update_success:
            return

        devices = coordinator.data.devices
        entities = []
        known_devices: set = config_entry.runtime_data.known_devices

        # Add entities for devices which we've not yet seen
        for device in devices:
            if (
                any(d.device_id == device.device_id for d in known_devices)
                or device.device_type != SH_DEVICE_TYPE_UID
            ):
                continue

            iotty_entity = IottyShutter(
                coordinator=coordinator,
                iotty_cloud=coordinator.iotty,
                iotty_device=Shutter(
                    device.device_id,
                    device.serial_number,
                    device.device_type,
                    device.device_name,
                ),
            )

            entities.extend([iotty_entity])
            known_devices.add(device)

        async_add_entities(entities)

    # Add a subscriber to the coordinator to discover new devices
    coordinator.async_add_listener(async_update_data)


class IottyShutter(CoverEntity, CoordinatorEntity[IottyDataUpdateCoordinator]):
    """Haas entity class for iotty Shutter."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_entity_category = None
    _attr_device_class = CoverDeviceClass.SHUTTER
    _iotty_cloud: IottyProxy
    _iotty_device: Shutter

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: Shutter,
    ) -> None:
        """Initialize the Shutter device."""
        super().__init__(coordinator=coordinator)

        _LOGGER.debug(
            "Creating new COVER (%s) %s",
            iotty_device.device_type,
            iotty_device.device_id,
        )

        self._iotty_cloud = iotty_cloud
        self._iotty_device = iotty_device
        self._attr_unique_id = iotty_device.device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, cast(str, self._attr_unique_id))},
            name=self._iotty_device.name,
            manufacturer="iotty",
        )

    @property
    def is_closed(self) -> bool:
        """Return true if the Shutter is closed."""
        _LOGGER.debug(
            "Retrieve device status for %s ? %s : %s",
            self._iotty_device.device_id,
            self._iotty_device.status,
            self._iotty_device.percentage,
        )
        return (
            self._iotty_device.status == ShutterState.STATIONARY
            and self._iotty_device.percentage == 0
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._iotty_device.status = ShutterState.OPENING
        await asyncio.sleep(1)
        self._iotty_device.percentage = 100
        self._iotty_device.status = ShutterState.STATIONARY
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._iotty_device.status = ShutterState.CLOSING
        await asyncio.sleep(1)
        self._iotty_device.percentage = 0
        self._iotty_device.status = ShutterState.STATIONARY
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        self._iotty_device.status = ShutterState.OPENING
        await asyncio.sleep(1)
        self._iotty_device.percentage = 50
        self._iotty_device.status = ShutterState.STATIONARY
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._iotty_device.status = ShutterState.STATIONARY
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        device: Device = next(
            device
            for device in self.coordinator.data.devices
            if device.device_id == self._iotty_device.device_id
        )
        if isinstance(device, Shutter):
            self._iotty_device.status = device.status
            self._iotty_device.percentage = device.percentage
        self.async_write_ha_state()
