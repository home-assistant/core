"""WJG Button Entities."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import WJGCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """PTZ-Buttons fuer einen Config-Entry registrieren."""
    coordinator: WJGCameraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WJGPTZButton(coordinator, entry, "up"),
            WJGPTZButton(coordinator, entry, "down"),
            WJGPTZButton(coordinator, entry, "left"),
            WJGPTZButton(coordinator, entry, "right"),
            WJGPTZButton(coordinator, entry, "zoom_in"),
            WJGPTZButton(coordinator, entry, "zoom_out"),
        ]
    )


class WJGPTZButton(CoordinatorEntity[WJGCameraCoordinator], ButtonEntity):
    """Button-Entity fuer PTZ-Steuerung."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WJGCameraCoordinator,
        entry: ConfigEntry,
        direction: str,
    ) -> None:
        """PTZ-Button fuer eine Richtung initialisieren."""
        super().__init__(coordinator)
        self._entry = entry
        self._direction = direction
        self._attr_unique_id = f"{entry.entry_id}_ptz_{direction}"
        self._attr_name = f"PTZ {self._direction.replace('_', ' ').title()}"
        self._attr_icon = self._icon_for_direction(direction)

    @property
    def device_info(self) -> DeviceInfo:
        """Zugehoerige Geraeteinformationen zurueckgeben."""
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    async def async_press(self) -> None:
        """PTZ-Befehl an den Coordinator weiterreichen."""
        ok = await self.coordinator.async_ptz_command(self._direction)
        if ok:
            _LOGGER.info(
                "PTZ-Befehl '%s' gesendet an %s",
                self._direction,
                self.coordinator.host,
            )
        else:
            _LOGGER.warning("PTZ-Befehl '%s' fehlgeschlagen", self._direction)

    def press(self) -> None:
        """Sync-API bewusst nicht unterstuetzen."""
        raise NotImplementedError("Use async_press instead")

    @staticmethod
    def _icon_for_direction(direction: str) -> str:
        """Passendes Icon fuer die PTZ-Richtung liefern."""
        icons = {
            "up": "mdi:arrow-up-bold-circle",
            "down": "mdi:arrow-down-bold-circle",
            "left": "mdi:arrow-left-bold-circle",
            "right": "mdi:arrow-right-bold-circle",
            "zoom_in": "mdi:magnify-plus",
            "zoom_out": "mdi:magnify-minus",
        }
        return icons.get(direction, "mdi:arrow-all")
