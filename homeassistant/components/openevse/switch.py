"""Support for OpenEVSE switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from openevsehttp import OpenEVSE

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import ATTR_CONNECTIONS, ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator
from .helpers import openevse_exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSESwitchDescription(SwitchEntityDescription):
    """Describes an OpenEVSE switch entity."""

    is_on_fn: Callable[[OpenEVSE], bool | None]
    turn_on_fn: Callable[[OpenEVSE], Awaitable[Any]]
    turn_off_fn: Callable[[OpenEVSE], Awaitable[Any]]


SWITCH_TYPES: tuple[OpenEVSESwitchDescription, ...] = (
    OpenEVSESwitchDescription(
        key="solar_pv_divert",
        translation_key="solar_pv_divert",
        is_on_fn=lambda ev: (
            ev.divertmode == "eco" if ev.divertmode is not None else None
        ),
        turn_on_fn=lambda ev: ev.set_divert_mode("eco"),
        turn_off_fn=lambda ev: ev.set_divert_mode(
            "fast"
        ),  # "fast" disables solar divert
    ),
    OpenEVSESwitchDescription(
        key="current_shaper",
        translation_key="current_shaper",
        is_on_fn=lambda ev: ev.shaper_active,
        turn_on_fn=lambda ev: ev.set_shaper(True),
        turn_off_fn=lambda ev: ev.set_shaper(False),
    ),
    OpenEVSESwitchDescription(
        key="manual_override",
        translation_key="manual_override",
        is_on_fn=lambda ev: ev.manual_override,
        turn_on_fn=lambda ev: ev.toggle_override(),
        turn_off_fn=lambda ev: ev.toggle_override(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE switches based on config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        OpenEVSESwitch(
            coordinator,
            description,
            entry.unique_id or entry.entry_id,
            entry.unique_id,
        )
        for description in SWITCH_TYPES
    )


class OpenEVSESwitch(CoordinatorEntity[OpenEVSEDataUpdateCoordinator], SwitchEntity):
    """Implementation of an OpenEVSE switch."""

    _attr_has_entity_name = True
    entity_description: OpenEVSESwitchDescription

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSESwitchDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.is_on_fn(self.coordinator.charger) is not None
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator.charger)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        with openevse_exception_handler():
            await self.entity_description.turn_on_fn(self.coordinator.charger)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        with openevse_exception_handler():
            await self.entity_description.turn_off_fn(self.coordinator.charger)
