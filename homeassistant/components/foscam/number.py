"""Foscam number platform for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from libpyfoscamcgi import FoscamCamera

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity


@dataclass(frozen=True, kw_only=True)
class FoscamNumberEntityDescription(NumberEntityDescription):
    """A custom entity description with adjustable features."""

    native_value_fn: Callable[[FoscamCoordinator], int]
    set_value_fn: Callable[[FoscamCamera, float], Any]
    exists_fn: Callable[[FoscamCoordinator], bool]


NUMBER_DESCRIPTIONS: list[FoscamNumberEntityDescription] = [
    FoscamNumberEntityDescription(
        key="device_volume",
        translation_key="device_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_value_fn=lambda coordinator: coordinator.data.device_volume,
        set_value_fn=lambda session, value: session.setAudioVolume(value),
        exists_fn=lambda coordinator: True,
    ),
    FoscamNumberEntityDescription(
        key="speak_volume",
        translation_key="speak_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_value_fn=lambda coordinator: coordinator.data.speak_volume,
        set_value_fn=lambda session, value: session.setSpeakVolume(value),
        exists_fn=lambda coordinator: coordinator.data.supports_speak_volume_adjustment,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up foscam number from a config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        FoscamVolumeNumberEntity(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
        if description.exists_fn is None or description.exists_fn(coordinator)
    )


class FoscamVolumeNumberEntity(FoscamEntity, NumberEntity):
    """Representation of a Foscam Smart AI number entity."""

    entity_description: FoscamNumberEntityDescription

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        description: FoscamNumberEntityDescription,
    ) -> None:
        """Initialize the data."""
        entry_id = coordinator.config_entry.entry_id
        super().__init__(coordinator, entry_id)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.entity_description.native_value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        self.hass.async_add_executor_job(
            self.entity_description.set_value_fn, self.coordinator.session, value
        )
        await self.coordinator.async_request_refresh()
