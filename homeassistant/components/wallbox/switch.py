"""Home Assistant component for accessing the Wallbox Portal API. The switch component creates a switch entity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WallboxCoordinator, WallboxEntity
from .const import (
    CHARGER_DATA_KEY,
    CHARGER_PAUSE_RESUME_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_STATUS_DESCRIPTION_KEY,
    DOMAIN,
    ChargerStatus,
)

SWITCH_TYPES: dict[str, SwitchEntityDescription] = {
    CHARGER_PAUSE_RESUME_KEY: SwitchEntityDescription(
        key=CHARGER_PAUSE_RESUME_KEY,
        name="Pause/Resume",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox sensor entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [WallboxSwitch(coordinator, entry, SWITCH_TYPES[CHARGER_PAUSE_RESUME_KEY])]
    )


class WallboxSwitch(WallboxEntity, SwitchEntity):
    """Representation of the Wallbox portal."""

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize a Wallbox switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{entry.title} {description.name}"
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def available(self) -> bool:
        """Return the availability of the switch."""
        return self.coordinator.data[CHARGER_STATUS_DESCRIPTION_KEY] not in {
            ChargerStatus.UNKNOWN,
            ChargerStatus.UPDATING,
            ChargerStatus.ERROR,
            ChargerStatus.LOCKED,
            ChargerStatus.LOCKED_CAR_CONNECTED,
            ChargerStatus.DISCONNECTED,
            ChargerStatus.READY,
        }

    @property
    def is_on(self) -> bool:
        """Return the status of pause/resume."""
        return self.coordinator.data[CHARGER_STATUS_DESCRIPTION_KEY] in {
            ChargerStatus.CHARGING,
            ChargerStatus.DISCHARGING,
            ChargerStatus.WAITING_FOR_CAR,
            ChargerStatus.WAITING,
        }

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause charger."""
        await self.coordinator.async_pause_charger(True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume charger."""
        await self.coordinator.async_pause_charger(False)
