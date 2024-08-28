"""Implement a iotty Light Switch Device."""

from __future__ import annotations

import logging
from typing import Any, cast

from iottycloud.device import Device
from iottycloud.lightswitch import LightSwitch
from iottycloud.verbs import LS_DEVICE_TYPE_UID

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Activate the iotty LightSwitch component."""
    _LOGGER.debug("Setup SWITCH entry id is %s", config_entry.entry_id)

    coordinator = config_entry.runtime_data.coordinator
    entities = [
        IottyLightSwitch(
            coordinator=coordinator, iotty_cloud=coordinator.iotty, iotty_device=d
        )
        for d in coordinator.data.devices
        if d.device_type == LS_DEVICE_TYPE_UID
        if (isinstance(d, LightSwitch))
    ]
    _LOGGER.debug("Found %d LightSwitches", len(entities))

    async_add_entities(entities)

    known_devices: set = config_entry.runtime_data.known_devices
    for known_device in coordinator.data.devices:
        if known_device.device_type == LS_DEVICE_TYPE_UID:
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
                or device.device_type != LS_DEVICE_TYPE_UID
            ):
                continue

            iotty_entity = IottyLightSwitch(
                coordinator=coordinator,
                iotty_cloud=coordinator.iotty,
                iotty_device=LightSwitch(
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


class IottyLightSwitch(SwitchEntity, CoordinatorEntity[IottyDataUpdateCoordinator]):
    """Haas entity class for iotty LightSwitch."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_entity_category = None
    _attr_device_class = SwitchDeviceClass.SWITCH
    _iotty_cloud: IottyProxy
    _iotty_device: LightSwitch

    def __init__(
        self,
        coordinator: IottyDataUpdateCoordinator,
        iotty_cloud: IottyProxy,
        iotty_device: LightSwitch,
    ) -> None:
        """Initialize the LightSwitch device."""
        super().__init__(coordinator=coordinator)

        _LOGGER.debug(
            "Creating new SWITCH (%s) %s",
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
    def is_on(self) -> bool:
        """Return true if the LightSwitch is on."""
        _LOGGER.debug(
            "Retrieve device status for %s ? %s",
            self._iotty_device.device_id,
            self._iotty_device.is_on,
        )
        return self._iotty_device.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LightSwitch on."""
        _LOGGER.debug("[%s] Turning on", self._iotty_device.device_id)
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_turn_on()
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LightSwitch off."""
        _LOGGER.debug("[%s] Turning off", self._iotty_device.device_id)
        await self._iotty_cloud.command(
            self._iotty_device.device_id, self._iotty_device.cmd_turn_off()
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
        if isinstance(device, LightSwitch):
            self._iotty_device.is_on = device.is_on
        self.async_write_ha_state()
