"""Support for VeSync numeric entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import get_humidifier_mode, is_humidifier
from .const import (
    DOMAIN,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_HUMIDIFIER_MODE_MANUAL,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VeSyncNumberEntityDescription(NumberEntityDescription):
    """Class to describe a Vesync number entity."""

    available_fn: Callable[[VeSyncBaseDevice], bool] | None = None
    """Callback to determine if the entity should be available."""
    exists_fn: Callable[[VeSyncBaseDevice], bool]
    """Callback to determine if an entity should be added for this description."""
    value_fn: Callable[[VeSyncBaseDevice], float]
    """Callback to return the value."""
    set_value_fn: Callable[[VeSyncBaseDevice, float], bool]
    """Callback to set the value."""


def is_humidifier_in_manual_mode(device: VeSyncBaseDevice) -> bool:
    """Get the humidifier mode."""

    return get_humidifier_mode(device) == VS_HUMIDIFIER_MODE_MANUAL


NUMBER_DESCRIPTIONS: list[VeSyncNumberEntityDescription] = [
    VeSyncNumberEntityDescription(
        key="mist_level",
        translation_key="mist_level",
        native_min_value=1,
        native_max_value=9,
        native_step=1,
        mode=NumberMode.SLIDER,
        available_fn=is_humidifier_in_manual_mode,
        exists_fn=is_humidifier,
        set_value_fn=lambda device, value: device.set_mist_level(value),
        value_fn=lambda device: device.mist_level,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_DEVICES], async_add_entities, coordinator)


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities: AddEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
):
    """Add number entities."""

    async_add_entities(
        VeSyncNumberEntity(dev, description, coordinator)
        for dev in devices
        for description in NUMBER_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncNumberEntity(VeSyncBaseEntity, NumberEntity):
    """A class to set numeric options on Vesync device."""

    entity_description: VeSyncNumberEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncNumberEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync number device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def native_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self.device)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if await self.hass.async_add_executor_job(
            self.entity_description.set_value_fn, self.device, value
        ):
            await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Check if device is available and the entity is applicable."""
        return super().available and (
            self.entity_description.available_fn is None
            or self.entity_description.available_fn(self.device)
        )
