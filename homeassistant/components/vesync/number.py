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

from .common import VeSyncBaseEntity, VeSyncDevice, is_humidifier
from .const import DOMAIN, VS_DISCOVERY, VS_NUMBERS

_LOGGER = logging.getLogger(__name__)


@dataclass
class VeSyncNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VeSyncBaseDevice], float]
    min_fn: Callable[[VeSyncBaseDevice], float]
    max_fn: Callable[[VeSyncBaseDevice], float]


@dataclass
class VeSyncNumberEntityDescription(
    NumberEntityDescription, VeSyncNumberEntityDescriptionMixin
):
    """Describe VeSync number entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool] = lambda device: True
    update_fn: Callable[[VeSyncBaseDevice, float], None] = lambda device, value: None


NUMBERS: tuple[VeSyncNumberEntityDescription, ...] = (
    VeSyncNumberEntityDescription(
        key="mist-level",
        name="Mist Level",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        min_fn=lambda device: float(device.config_dict["mist_levels"][0]),
        max_fn=lambda device: float(device.config_dict["mist_levels"][-1]),
        value_fn=lambda device: device.details["mist_virtual_level"],
        update_fn=lambda device, value: device.set_mist_level(int(value)),
        exists_fn=lambda device: is_humidifier(device.device_type),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers."""

    async def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_NUMBERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_NUMBERS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        for description in NUMBERS:
            if description.exists_fn(dev):
                entities.append(VeSyncNumberEntity(dev, description))

    async_add_entities(entities, update_before_add=True)


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
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self.entity_description.min_fn(self.device)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.entity_description.max_fn(self.device)

    @property
    def native_value(self) -> float | None:
        """Return the value of the number."""
        return self.entity_description.value_fn(self.device)

    def set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        self.entity_description.update_fn(self.device, value)
