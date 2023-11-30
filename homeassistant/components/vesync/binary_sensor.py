"""Support for power & energy sensors for VeSync outlets."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    DEVICE_HELPER,
    VeSyncBaseEntity,
    VeSyncDevice,
    VeSyncEntityDescriptionFactory,
)
from .const import DOMAIN, VS_BINARY_SENSORS, VS_DISCOVERY

_LOGGER = logging.getLogger(__name__)


@dataclass
class VeSyncBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VeSyncBaseDevice], bool]


@dataclass
class VeSyncBinarySensorEntityDescription(
    BinarySensorEntityDescription, VeSyncBinarySensorEntityDescriptionMixin
):
    """Describe VeSync binary_sensor entity."""


class EmptyWaterTankEntityDescriptionFactory(
    VeSyncEntityDescriptionFactory[VeSyncBinarySensorEntityDescription]
):
    """Create an entity description for a device that supports empty water tank sensor."""

    def create(self, device: VeSyncBaseDevice) -> VeSyncBinarySensorEntityDescription:
        """Create a VeSyncNumberEntityDescription."""
        return VeSyncBinarySensorEntityDescription(
            key="water_lacks",
            name="Empty Water Tank",
            icon="mdi:water-alert",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda device: DEVICE_HELPER.get_feature(
                device, "details", "water_lacks"
            ),
        )

    def supports(self, device: VeSyncBaseDevice) -> bool:
        """Determine if this device supports a water_lacks property."""
        return DEVICE_HELPER.has_feature(device, "details", "water_lacks")


class WaterTankLiftedEntityDescriptionFactory(
    VeSyncEntityDescriptionFactory[VeSyncBinarySensorEntityDescription]
):
    """Create an entity description for a device that supports water tank lifted sensor."""

    def create(self, device: VeSyncBaseDevice) -> VeSyncBinarySensorEntityDescription:
        """Create a VeSyncNumberEntityDescription."""
        return VeSyncBinarySensorEntityDescription(
            key="water_tank_lifted",
            name="Water Tank Lifted",
            icon="mdi:water-alert",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda device: DEVICE_HELPER.get_feature(
                device, "details", "water_tank_lifted"
            ),
        )

    def supports(self, device: VeSyncBaseDevice) -> bool:
        """Determine if this device supports a water_tank_lifted property."""
        return DEVICE_HELPER.has_feature(device, "details", "water_tank_lifted")


class HighHumidityEntityDescriptionFactory(
    VeSyncEntityDescriptionFactory[VeSyncBinarySensorEntityDescription]
):
    """Create an entity description for a device that supports high humidity sensor."""

    def create(self, device: VeSyncBaseDevice) -> VeSyncBinarySensorEntityDescription:
        """Create a VeSyncNumberEntityDescription."""
        return VeSyncBinarySensorEntityDescription(
            key="humidity_high",
            name="Humidity High",
            icon="mdi:water-percent-alert",
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda device: DEVICE_HELPER.get_feature(
                device, "details", "humidity_high"
            ),
        )

    def supports(self, device: VeSyncBaseDevice) -> bool:
        """Determine if this device supports a humidity_high property."""
        return DEVICE_HELPER.has_feature(device, "details", "humidity_high")


_FACTORIES: list[VeSyncEntityDescriptionFactory] = [
    EmptyWaterTankEntityDescriptionFactory(),
    WaterTankLiftedEntityDescriptionFactory(),
    HighHumidityEntityDescriptionFactory(),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    @callback
    def discover(devices: list):
        """Add new devices to platform."""
        entities = []
        for dev in devices:
            supported = False
            for factory in _FACTORIES:
                if factory.supports(dev):
                    supported = True
                    entities.append(VeSyncBinarySensorEntity(dev, factory.create(dev)))

            if not supported:
                # if no factory supported a property of the device
                _LOGGER.warning(
                    "%s - Unsupported device type - %s",
                    dev.device_name,
                    dev.device_type,
                )

        async_add_entities(entities, update_before_add=True)

    discover(hass.data[DOMAIN][VS_BINARY_SENSORS])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_BINARY_SENSORS), discover)
    )


class VeSyncBinarySensorEntity(VeSyncBaseEntity, BinarySensorEntity):
    """Representation of a binary sensor describing diagnostics of a VeSync device."""

    entity_description: VeSyncBinarySensorEntityDescription

    def __init__(
        self, device: VeSyncDevice, description: VeSyncBinarySensorEntityDescription
    ) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{super().name} {description.name}"
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.device)
