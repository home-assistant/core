"""Switch platform for Indevolt integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IndevoltConfigEntry
from .coordinator import IndevoltCoordinator
from .entity import IndevoltEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IndevoltSwitchEntityDescription(SwitchEntityDescription):
    """Custom entity description class for Indevolt switch entities."""

    read_key: str
    write_key: str
    read_on_value: int = 1
    read_off_value: int = 0
    generation: list[int] = field(default_factory=lambda: [1, 2])


SWITCHES: Final = (
    IndevoltSwitchEntityDescription(
        key="grid_charging",
        translation_key="grid_charging",
        generation=[2],
        read_key="2618",
        write_key="1143",
        read_on_value=1001,
        read_off_value=1000,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    IndevoltSwitchEntityDescription(
        key="light",
        translation_key="light",
        generation=[2],
        read_key="7171",
        write_key="7265",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    IndevoltSwitchEntityDescription(
        key="bypass",
        translation_key="bypass",
        generation=[2],
        read_key="680",
        write_key="7266",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IndevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform for Indevolt."""
    coordinator = entry.runtime_data
    device_gen = coordinator.generation

    # Switch initialization
    async_add_entities(
        IndevoltSwitchEntity(coordinator=coordinator, description=description)
        for description in SWITCHES
        if device_gen in description.generation
    )


class IndevoltSwitchEntity(IndevoltEntity, SwitchEntity):
    """Represents a switch entity for Indevolt devices."""

    entity_description: IndevoltSwitchEntityDescription

    def __init__(
        self,
        coordinator: IndevoltCoordinator,
        description: IndevoltSwitchEntityDescription,
    ) -> None:
        """Initialize the Indevolt switch entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{self.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        raw_value = self.coordinator.data.get(self.entity_description.read_key)
        if raw_value is None:
            return None

        if raw_value == self.entity_description.read_on_value:
            return True

        if raw_value == self.entity_description.read_off_value:
            return False

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_toggle(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_toggle(0)

    async def _async_toggle(self, value: int) -> None:
        """Toggle the switch on/off."""
        success = await self.coordinator.async_push_data(
            self.entity_description.write_key, value
        )

        if success:
            await self.coordinator.async_request_refresh()

        else:
            raise HomeAssistantError(f"Failed to set value {value} for {self.name}")
