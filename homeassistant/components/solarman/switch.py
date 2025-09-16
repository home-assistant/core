"""Creates switch entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import SolarmanEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True)
class SolarmanSwitchEntityDescription(SwitchEntityDescription):
    """Class to describe a sensor entity."""

    name: str = ""
    sub_key: str = ""


SWITCHES = [
    SolarmanSwitchEntityDescription(
        key="power_on", 
        translation_key="smart_plug",
        sub_key="SP-2W-EU", 
        device_class=SwitchDeviceClass.OUTLET
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    entities = [
        SolarmanSwitchEntity(entry.runtime_data, description)
        for description in SWITCHES
        if description.sub_key == entry.data.get("model")
    ]

    if entities:
        async_add_entities(entities)


class SolarmanSwitchEntity(SolarmanEntity, SwitchEntity):
    """Representation of a Solarman switch."""

    def __init__(
        self, coordinator, description: SolarmanSwitchEntityDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.config_entry.unique_id}_{description.key}"
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        status = self.coordinator.data.get("switch_status")
        if status == "on":
            return True
        if status == "off":
            return False
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.set_power_state(True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.set_power_state(False)
        await self.coordinator.async_refresh()
