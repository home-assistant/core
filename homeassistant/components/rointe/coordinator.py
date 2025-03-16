"""Provides the Rointe DataUpdateCoordinator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from rointesdk.device import RointeDevice

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, PLATFORMS
from .device_manager import RointeDeviceManager

ROINTE_API_REFRESH_INTERVAL = timedelta(seconds=15)


@dataclass
class RointeSensorEntityDescriptionMixin:
    """Define a description mixin for Rointe sensor entities."""

    last_reset_fn: Callable[[RointeDevice], datetime | None]
    name_fn: Callable[[RointeDevice], str]
    value_fn: Callable[[RointeDevice], StateType]


@dataclass
class RointeSensorEntityDescription(
    SensorEntityDescription, RointeSensorEntityDescriptionMixin
):
    """Define an object to describe Rointe sensor entities."""


class RointeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RointeDevice]]):
    """Rointe data coordinator."""

    def __init__(
        self, hass: HomeAssistant, device_manager: RointeDeviceManager
    ) -> None:
        """Initialize Rointe data updater."""
        self.device_manager = device_manager
        self.unregistered_keys: dict[str, dict[str, RointeDevice]] = {}

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=ROINTE_API_REFRESH_INTERVAL,
        )

        self.unregistered_keys = {platform: {} for platform in PLATFORMS}

    async def _async_update_data(self) -> dict[str, RointeDevice]:
        """Fetch data from API."""

        new_devices = await self.device_manager.update()

        for platform in PLATFORMS:
            self.unregistered_keys[platform].update(
                {
                    device_id: device
                    for device_id, device in new_devices.items()
                    if device_id not in self.unregistered_keys[platform]
                }
            )

        for device in new_devices.values():
            device_update_info(self.hass, device)

        return new_devices

    @callback
    def add_entities_for_seen_keys(
        self,
        async_add_entities: AddEntitiesCallback,
        entity_constructor_list: list[Any],
        platform: str,
    ) -> None:
        """Add entities for new devices, for a given platform.

        Called from a platform's `async_setup_entry`.
        """

        discovered_devices: dict[str, RointeDevice] = self.data

        if not discovered_devices:
            return

        new_entities: list = []

        for device_id, device in discovered_devices.items():
            if device_id in self.unregistered_keys[platform]:
                new_entities.extend(
                    [
                        constructor(device, self)
                        for constructor in entity_constructor_list
                    ]
                )

                self.unregistered_keys[platform].pop(device_id)

        if new_entities:
            async_add_entities(new_entities)

    @callback
    def add_sensor_entities_for_seen_keys(
        self,
        async_add_entities: AddEntitiesCallback,
        sensor_descriptions: list[RointeSensorEntityDescription],
        sensor_constructor: type,
    ) -> None:
        """Add entities for new sensors from a list of entity descriptions."""

        discovered_devices: dict[str, RointeDevice] = self.data

        if not discovered_devices:
            return

        new_entities: list = []

        for device_id, device in discovered_devices.items():
            if device_id in self.unregistered_keys[Platform.SENSOR]:
                new_entities.extend(
                    [
                        sensor_constructor(device, self, sensor_description)
                        for sensor_description in sensor_descriptions
                    ]
                )

                self.unregistered_keys[Platform.SENSOR].pop(device_id)

        if new_entities:
            async_add_entities(new_entities)


@callback
def device_update_info(hass: HomeAssistant, rointe_device: RointeDevice) -> None:
    """Update device registry info."""

    LOGGER.debug("Updating device registry info for %s", rointe_device.name)

    dev_registry = dr.async_get(hass)

    if device := dev_registry.async_get_device(
        identifiers={(DOMAIN, rointe_device.id)},
    ):
        dev_registry.async_update_device(
            device.id, sw_version=rointe_device.firmware_version
        )
