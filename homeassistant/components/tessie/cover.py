"""Cover platform for Tessie integration."""
from __future__ import annotations

from typing import Any

from tessie_api import (
    close_charge_port,
    close_windows,
    open_unlock_charge_port,
    vent_windows,
)

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        Entity(coordinator)
        for Entity in (
            TessieWindowEntity,
            TessieChargePortEntity,
        )
        for coordinator in coordinators
    )


class TessieWindowEntity(TessieEntity, CoverEntity):
    """Cover entity for current charge."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator: TessieDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "windows")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return (
            self.get("vehicle_state_fd_window") == 0
            and self.get("vehicle_state_fp_window") == 0
            and self.get("vehicle_state_rd_window") == 0
            and self.get("vehicle_state_rp_window") == 0
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open windows."""
        await self.run(vent_windows)
        self.set(
            ("vehicle_state_fd_window", 1),
            ("vehicle_state_fp_window", 1),
            ("vehicle_state_rd_window", 1),
            ("vehicle_state_rp_window", 1),
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        await self.run(close_windows)
        self.set(
            ("vehicle_state_fd_window", 0),
            ("vehicle_state_fp_window", 0),
            ("vehicle_state_rd_window", 0),
            ("vehicle_state_rp_window", 0),
        )


class TessieChargePortEntity(TessieEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator: TessieDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "charge_state_charge_port_door_open")

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return not self._value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open windows."""
        await self.run(open_unlock_charge_port)
        self.set((self.key, True))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        await self.run(close_charge_port)
        self.set((self.key, False))
