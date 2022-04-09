"""Home Assistant component for accessing the Wallbox Portal API. The lock component creates a switch entity."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WallboxCoordinator, WallboxEntity
from .const import (
    CONF_DATA_KEY,
    CONF_PAUSE_RESUME_KEY,
    CONF_SERIAL_NUMBER_KEY,
    CONF_STATUS_DESCRIPTION_KEY,
    DOMAIN,
)


@dataclass
class WallboxSwitchEntityDescription(SwitchEntityDescription):
    """Describes Wallbox sensor entity."""


SWITCH_TYPES: dict[str, WallboxSwitchEntityDescription] = {
    CONF_PAUSE_RESUME_KEY: WallboxSwitchEntityDescription(
        key=CONF_PAUSE_RESUME_KEY, name="Pause/Resume"
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox sensor entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [WallboxSwitch(coordinator, entry, SWITCH_TYPES[CONF_PAUSE_RESUME_KEY])]
    )


class WallboxSwitch(WallboxEntity, SwitchEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSwitchEntityDescription
    coordinator: WallboxCoordinator

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: WallboxSwitchEntityDescription,
    ) -> None:
        """Initialize a Wallbox switch."""

        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_name = f"{entry.title} {description.name}"
        self._attr_unique_id = f"{description.key}-{coordinator.data[CONF_DATA_KEY][CONF_SERIAL_NUMBER_KEY]}"

    @property
    def available(self) -> bool:
        """Return the availability of the switch."""
        return self.coordinator.data[CONF_STATUS_DESCRIPTION_KEY].lower() in [
            "charging",
            "paused",
        ]

    @property
    def is_on(self) -> bool:
        """Return the status of pause/resume."""
        return self._coordinator.data[CONF_STATUS_DESCRIPTION_KEY].lower == "charging"  # type: ignore[no-any-return]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause charger."""
        await self._coordinator.async_pause_charger(True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume charger."""
        await self.coordinator.async_pause_charger(False)
