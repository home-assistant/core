"""Support for voltage, power & energy sensors for VeSync outlets."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncfan import VeSyncAirBypass
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncSwitch

from homeassistant.components.binary_sensor import (
    # BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

# BinarySensorStateClass,
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .common import VeSyncBaseEntity
from .const import DOMAIN, SKU_TO_BASE_DEVICE, VS_BINARY_SENSORS, VS_DISCOVERY

_LOGGER = logging.getLogger(__name__)


@dataclass
class VeSyncBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], StateType]


@dataclass
class VeSyncBinarySensorEntityDescription(
    BinarySensorEntityDescription, VeSyncBinarySensorEntityDescriptionMixin
):
    """Describe VeSync sensor entity."""

    exists_fn: Callable[
        [VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], bool
    ] = lambda _: True
    update_fn: Callable[
        [VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], None
    ] = lambda _: None


def sku_supported(device, supported) -> bool:
    """Get the base device of which a device is an instance."""
    return SKU_TO_BASE_DEVICE.get(device.device_type) in supported


LIGHT_DETECTION_SUPPORTED = ["Vital200S"]

BINARY_SENSORS: tuple[VeSyncBinarySensorEntityDescription, ...] = (
    VeSyncBinarySensorEntityDescription(
        key="light-detected",
        translation_key="light_detected",
        icon="mdi:lightbulb-question-outline",
        # We need to inverse the state, since the attribute is
        # * False when light is detected
        # * True when NO light is detected
        value_fn=lambda device: not device.light_detection_state,
        exists_fn=lambda device: sku_supported(device, LIGHT_DETECTION_SUPPORTED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_BINARY_SENSORS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_BINARY_SENSORS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []

    for dev in devices:
        for description in BINARY_SENSORS:
            if description.exists_fn(dev):
                entities.append(VeSyncBinarySensorEntity(dev, description))
    async_add_entities(entities, update_before_add=True)


class VeSyncBinarySensorEntity(VeSyncBaseEntity, BinarySensorEntity):
    """Representation of a binary sensor describing a VeSync device."""

    entity_description: VeSyncBinarySensorEntityDescription

    def __init__(
        self,
        device: VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch,
        description: VeSyncBinarySensorEntityDescription,
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return bool(self.entity_description.value_fn(self.device))

    def update(self) -> None:
        """Run the update function defined for the sensor."""
        return self.entity_description.update_fn(self.device)
