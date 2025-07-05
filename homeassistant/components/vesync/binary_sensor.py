"""Binary Sensor for VeSync."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import rgetattr
from .const import DOMAIN, VS_COORDINATOR, VS_DEVICES, VS_DISCOVERY, VS_MANAGER
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VeSyncBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A class that describes custom binary sensor entities."""

    is_on: Callable[[VeSyncBaseDevice], bool]


SENSOR_DESCRIPTIONS: tuple[VeSyncBinarySensorEntityDescription, ...] = (
    VeSyncBinarySensorEntityDescription(
        key="state.water_lacks",
        translation_key="water_lacks",
        is_on=lambda device: device.state.water_lacks,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    VeSyncBinarySensorEntityDescription(
        key="state.water_tank_lifted",
        translation_key="water_tank_lifted",
        is_on=lambda device: device.state.water_tank_lifted,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][VS_MANAGER].devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(devices, async_add_entities, coordinator):
    """Add entity."""
    async_add_entities(
        (
            VeSyncBinarySensor(dev, description, coordinator)
            for dev in devices
            for description in SENSOR_DESCRIPTIONS
            if rgetattr(dev, description.key) is not None
        ),
    )


class VeSyncBinarySensor(BinarySensorEntity, VeSyncBaseEntity):
    """Vesync binary sensor class."""

    entity_description: VeSyncBinarySensorEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncBinarySensorEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on(self.device)
