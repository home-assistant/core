"""Support for number settings on VeSync devices."""
from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncBaseEntity, VeSyncDevice, VeSyncEntityDescriptionFactory
from .const import DOMAIN, VS_DISCOVERY, VS_NUMBERS

_LOGGER = logging.getLogger(__name__)


@dataclass
class VeSyncNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VeSyncBaseDevice], float]


@dataclass
class VeSyncNumberEntityDescription(
    NumberEntityDescription, VeSyncNumberEntityDescriptionMixin
):
    """Describe VeSync number entity."""

    update_fn: Callable[[VeSyncBaseDevice, float], None] = lambda device, value: None


class MistLevelEntityDescriptionFactory(
    VeSyncEntityDescriptionFactory[VeSyncNumberEntityDescription]
):
    """Create an entity description for a device that supports mist levels."""

    def create(self, device: VeSyncBaseDevice) -> VeSyncNumberEntityDescription:
        """Create a VeSyncNumberEntityDescription."""
        return VeSyncNumberEntityDescription(
            key="mist-level",
            name="Mist Level",
            entity_category=EntityCategory.CONFIG,
            native_step=1,
            value_fn=lambda device: device.details["mist_virtual_level"],
            update_fn=lambda device, value: device.set_mist_level(int(value)),
            native_min_value=float(device.config_dict["mist_levels"][0]),
            native_max_value=float(device.config_dict["mist_levels"][-1]),
        )

    def supports(self, device: VeSyncBaseDevice) -> bool:
        """Determine if this device supports a mist_virtual_level property."""
        return "mist_virtual_level" in device.details


_FACTORIES: list[VeSyncEntityDescriptionFactory] = [
    MistLevelEntityDescriptionFactory(),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers."""

    @callback
    def discover(devices: list):
        """Add new devices to platform."""
        entities = []
        for dev in devices:
            supported = False
            for factory in _FACTORIES:
                if factory.supports(dev):
                    supported = True
                    entities.append(VeSyncNumberEntity(dev, factory.create(dev)))

            if not supported:
                # if no factory supported a property of the device
                _LOGGER.warning(
                    "%s - Unsupported device type - %s",
                    dev.device_name,
                    dev.device_type,
                )

        async_add_entities(entities, update_before_add=True)

    discover(hass.data[DOMAIN][VS_NUMBERS])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_NUMBERS), discover)
    )


class VeSyncNumberEntity(VeSyncBaseEntity, NumberEntity):
    """Representation of a number for configuring a VeSync device."""

    entity_description: VeSyncNumberEntityDescription

    def __init__(
        self, device: VeSyncDevice, description: VeSyncNumberEntityDescription
    ) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{super().name} {description.name}"
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the value of the number."""
        return self.entity_description.value_fn(self.device)

    def set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        self.entity_description.update_fn(self.device, value)
