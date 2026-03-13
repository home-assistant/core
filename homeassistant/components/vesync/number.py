"""Support for VeSync numeric entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import get_timer_remaining_minutes, is_humidifier, supports_timer
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _mist_levels(device: VeSyncBaseDevice) -> list[int]:
    """Check if the device supports mist level adjustment."""
    if is_humidifier(device):
        return device.mist_levels
    raise HomeAssistantError("Device does not support mist level adjustment.")


def _set_mist_level(device: VeSyncBaseDevice, value: float) -> Awaitable[bool]:
    """Set mist level on humidifier."""
    if is_humidifier(device):
        return device.set_mist_level(int(value))
    raise HomeAssistantError("Device does not support mist level adjustment.")


def _warm_mist_levels(device: VeSyncBaseDevice) -> list[int]:
    """Return warm mist levels for devices that support warm mist."""
    if is_humidifier(device) and device.supports_warm_mist:
        return device.warm_mist_levels
    raise HomeAssistantError("Device does not support warm mist level adjustment.")


def _set_warm_mist_level(device: VeSyncBaseDevice, value: float) -> Awaitable[bool]:
    """Set warm mist level on humidifier."""
    if is_humidifier(device) and device.supports_warm_mist:
        return device.set_warm_level(int(value))
    raise HomeAssistantError("Device does not support warm mist level adjustment.")


def _set_timer(device: VeSyncBaseDevice, value: float) -> Awaitable[bool]:
    """Set timer duration in minutes."""
    if not supports_timer(device):
        raise HomeAssistantError("Device does not support timer adjustment.")
    return device.set_timer(int(value * 60.0))


@dataclass(frozen=True, kw_only=True)
class VeSyncNumberEntityDescription(NumberEntityDescription):
    """Class to describe a Vesync number entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool] = lambda _: True
    value_fn: Callable[[VeSyncBaseDevice], float]
    native_min_value_fn: Callable[[VeSyncBaseDevice], float]
    native_max_value_fn: Callable[[VeSyncBaseDevice], float]
    set_value_fn: Callable[[VeSyncBaseDevice, float], Awaitable[bool]]


def _warm_mist_value(device: VeSyncBaseDevice) -> float:
    """Return current warm mist level, or min level if state not yet available."""
    level = device.state.warm_mist_level
    if level is not None:
        return float(level)
    levels = _warm_mist_levels(device)
    return float(min(levels))


NUMBER_DESCRIPTIONS: list[VeSyncNumberEntityDescription] = [
    VeSyncNumberEntityDescription(
        key="mist_level",
        translation_key="mist_level",
        native_min_value_fn=lambda device: min(_mist_levels(device)),
        native_max_value_fn=lambda device: max(_mist_levels(device)),
        native_step=1,
        mode=NumberMode.SLIDER,
        exists_fn=is_humidifier,
        set_value_fn=_set_mist_level,
        value_fn=lambda device: device.state.mist_virtual_level,
    ),
    VeSyncNumberEntityDescription(
        key="warm_mist_level",
        translation_key="warm_mist_level",
        native_min_value_fn=lambda device: min(_warm_mist_levels(device)),
        native_max_value_fn=lambda device: max(_warm_mist_levels(device)),
        native_step=1,
        mode=NumberMode.SLIDER,
        exists_fn=lambda device: is_humidifier(device) and device.supports_warm_mist,
        set_value_fn=_set_warm_mist_level,
        value_fn=_warm_mist_value,
    ),
    VeSyncNumberEntityDescription(
        key="timer_duration",
        translation_key="timer_duration",
        native_min_value_fn=lambda _: 0.0,
        native_max_value_fn=lambda _: 720.0,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        exists_fn=supports_timer,
        set_value_fn=_set_timer,
        value_fn=get_timer_remaining_minutes,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
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

    @property
    def native_min_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_min_value_fn(self.device)

    @property
    def native_max_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_max_value_fn(self.device)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not await self.entity_description.set_value_fn(self.device, value):
            raise HomeAssistantError(self.device.last_response.message)
        self.async_write_ha_state()
