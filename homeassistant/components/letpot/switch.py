"""Support for LetPot switch entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from letpot.deviceclient import LetPotDeviceClient
from letpot.models import DeviceFeature, LetPotDeviceStatus

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LetPotConfigEntry
from .coordinator import LetPotDeviceCoordinator
from .entity import LetPotEntity

# Each change pushes a 'full' device status with the change. The library will cache
# pending changes to avoid overwriting, but try to avoid a lot of parallelism.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LetPotSwitchEntityDescription(SwitchEntityDescription):
    """Describes a LetPot switch entity."""

    value_fn: Callable[[LetPotDeviceStatus], bool | None]
    set_value_fn: Callable[[LetPotDeviceClient, bool], Coroutine[Any, Any, None]]


BASE_SWITCHES: tuple[LetPotSwitchEntityDescription, ...] = (
    LetPotSwitchEntityDescription(
        key="power",
        translation_key="power",
        value_fn=lambda status: None if status is None else status.system_on,
        set_value_fn=lambda device_client, value: device_client.set_power(value),
        entity_category=EntityCategory.CONFIG,
    ),
    LetPotSwitchEntityDescription(
        key="pump_cycling",
        translation_key="pump_cycling",
        value_fn=lambda status: None if status is None else status.pump_mode == 1,
        set_value_fn=lambda device_client, value: device_client.set_pump_mode(value),
        entity_category=EntityCategory.CONFIG,
    ),
)
ALARM_SWITCH: LetPotSwitchEntityDescription = LetPotSwitchEntityDescription(
    key="alarm_sound",
    translation_key="alarm_sound",
    value_fn=lambda status: None if status is None else status.system_sound,
    set_value_fn=lambda device_client, value: device_client.set_sound(value),
    entity_category=EntityCategory.CONFIG,
)
AUTO_MODE_SWITCH: LetPotSwitchEntityDescription = LetPotSwitchEntityDescription(
    key="auto_mode",
    translation_key="auto_mode",
    value_fn=lambda status: None if status is None else status.water_mode == 1,
    set_value_fn=lambda device_client, value: device_client.set_water_mode(value),
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LetPot switch entities based on a config entry and device status/features."""
    coordinators = entry.runtime_data
    entities: list[SwitchEntity] = [
        LetPotSwitchEntity(coordinator, description)
        for description in BASE_SWITCHES
        for coordinator in coordinators
    ]
    entities.extend(
        LetPotSwitchEntity(coordinator, ALARM_SWITCH)
        for coordinator in coordinators
        if coordinator.data.system_sound is not None
    )
    entities.extend(
        LetPotSwitchEntity(coordinator, AUTO_MODE_SWITCH)
        for coordinator in coordinators
        if DeviceFeature.PUMP_AUTO in coordinator.device_client.device_features
    )
    async_add_entities(entities)


class LetPotSwitchEntity(LetPotEntity, SwitchEntity):
    """Defines a LetPot switch entity."""

    entity_description: LetPotSwitchEntityDescription

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator,
        description: LetPotSwitchEntityDescription,
    ) -> None:
        """Initialize LetPot switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{coordinator.device.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return if the entity is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.entity_description.set_value_fn(self.coordinator.device_client, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_description.set_value_fn(
            self.coordinator.device_client, False
        )
