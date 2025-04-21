"""Implement a iotty Shutter Device."""

from __future__ import annotations

import logging
from typing import Any

from iottycloud.device import Device
from iottycloud.shutter import Shutter, ShutterState
from iottycloud.verbs import SH_DEVICE_TYPE_UID

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import IottyProxy
from .coordinator import IottyConfigEntry, IottyDataUpdateCoordinator
from .entity import IottyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IottyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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


class IottyShutter(IottyEntity, CoverEntity):
    """Haas entity class for iotty Shutter."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _iotty_device: Shutter
    _attr_supported_features: CoverEntityFeature = CoverEntityFeature(0) | (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: Shutter,
    ) -> None:
        """Initialize the Shutter device."""
        super().__init__(coordinator, iotty_cloud, iotty_device)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the shutter.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._iotty_device.percentage

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

    @property
    def is_opening(self) -> bool:
        """Return true if the Shutter is opening."""
        return self._iotty_device.status == ShutterState.OPENING

    @property
    def is_closing(self) -> bool:
        """Return true if the Shutter is closing."""
        return self._iotty_device.status == ShutterState.CLOSING

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_open()
        )
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_close()
        )
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        percentage = kwargs[ATTR_POSITION]
        await self._iotty_cloud.command(
            self._iotty_device.device_id,
            self._iotty_device.cmd_move_to(),
            {"open_percentage": percentage},
        )
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_stop()
        )
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
            self._iotty_device = device
        self.async_write_ha_state()
