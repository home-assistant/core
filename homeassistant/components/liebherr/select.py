"""Select platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pyliebherrhomeapi import (
    BioFreshPlusControl,
    BioFreshPlusMode,
    HydroBreezeControl,
    HydroBreezeMode,
    IceMakerControl,
    IceMakerMode,
    ZonePosition,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import ZONE_POSITION_MAP, LiebherrEntity

PARALLEL_UPDATES = 1

type SelectControl = IceMakerControl | HydroBreezeControl | BioFreshPlusControl


@dataclass(frozen=True, kw_only=True)
class LiebherrSelectEntityDescription(SelectEntityDescription):
    """Describes a Liebherr select entity."""

    control_type: type[SelectControl]
    mode_enum: type[StrEnum]
    current_mode_fn: Callable[[SelectControl], StrEnum | str | None]
    options_fn: Callable[[SelectControl], list[str]]
    set_fn: Callable[[LiebherrCoordinator, int, StrEnum], Coroutine[Any, Any, None]]


def _ice_maker_options(control: SelectControl) -> list[str]:
    """Return available ice maker options."""
    if TYPE_CHECKING:
        assert isinstance(control, IceMakerControl)
    options = [IceMakerMode.OFF.value, IceMakerMode.ON.value]
    if control.has_max_ice:
        options.append(IceMakerMode.MAX_ICE.value)
    return options


def _hydro_breeze_options(control: SelectControl) -> list[str]:
    """Return available HydroBreeze options."""
    return [mode.value for mode in HydroBreezeMode]


def _bio_fresh_plus_options(control: SelectControl) -> list[str]:
    """Return available BioFresh-Plus options."""
    if TYPE_CHECKING:
        assert isinstance(control, BioFreshPlusControl)
    return [
        mode.value
        for mode in control.supported_modes
        if isinstance(mode, BioFreshPlusMode)
    ]


SELECT_TYPES: list[LiebherrSelectEntityDescription] = [
    LiebherrSelectEntityDescription(
        key="ice_maker",
        translation_key="ice_maker",
        control_type=IceMakerControl,
        mode_enum=IceMakerMode,
        current_mode_fn=lambda c: c.ice_maker_mode,  # type: ignore[union-attr]
        options_fn=_ice_maker_options,
        set_fn=lambda coordinator, zone_id, mode: coordinator.client.set_ice_maker(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            mode=mode,  # type: ignore[arg-type]
        ),
    ),
    LiebherrSelectEntityDescription(
        key="hydro_breeze",
        translation_key="hydro_breeze",
        control_type=HydroBreezeControl,
        mode_enum=HydroBreezeMode,
        current_mode_fn=lambda c: c.current_mode,  # type: ignore[union-attr]
        options_fn=_hydro_breeze_options,
        set_fn=lambda coordinator, zone_id, mode: coordinator.client.set_hydro_breeze(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            mode=mode,  # type: ignore[arg-type]
        ),
    ),
    LiebherrSelectEntityDescription(
        key="bio_fresh_plus",
        translation_key="bio_fresh_plus",
        control_type=BioFreshPlusControl,
        mode_enum=BioFreshPlusMode,
        current_mode_fn=lambda c: c.current_mode,  # type: ignore[union-attr]
        options_fn=_bio_fresh_plus_options,
        set_fn=lambda coordinator, zone_id, mode: coordinator.client.set_bio_fresh_plus(
            device_id=coordinator.device_id,
            zone_id=zone_id,
            mode=mode,  # type: ignore[arg-type]
        ),
    ),
]


def _create_select_entities(
    coordinators: list[LiebherrCoordinator],
) -> list[LiebherrSelectEntity]:
    """Create select entities for the given coordinators."""
    entities: list[LiebherrSelectEntity] = []

    for coordinator in coordinators:
        has_multiple_zones = len(coordinator.data.get_temperature_controls()) > 1

        for control in coordinator.data.controls:
            for description in SELECT_TYPES:
                if isinstance(control, description.control_type):
                    if TYPE_CHECKING:
                        assert isinstance(
                            control,
                            IceMakerControl | HydroBreezeControl | BioFreshPlusControl,
                        )
                    entities.append(
                        LiebherrSelectEntity(
                            coordinator=coordinator,
                            description=description,
                            zone_id=control.zone_id,
                            has_multiple_zones=has_multiple_zones,
                        )
                    )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr select entities."""
    async_add_entities(
        _create_select_entities(list(entry.runtime_data.coordinators.values()))
    )

    @callback
    def _async_new_device(coordinators: list[LiebherrCoordinator]) -> None:
        """Add select entities for new devices."""
        async_add_entities(_create_select_entities(coordinators))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_device_{entry.entry_id}", _async_new_device
        )
    )


class LiebherrSelectEntity(LiebherrEntity, SelectEntity):
    """Representation of a Liebherr select entity."""

    entity_description: LiebherrSelectEntityDescription

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        description: LiebherrSelectEntityDescription,
        zone_id: int,
        has_multiple_zones: bool,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}_{zone_id}"

        # Set options from the control
        control = self._select_control
        if control is not None:
            self._attr_options = description.options_fn(control)

        # Add zone suffix only for multi-zone devices
        if has_multiple_zones:
            temp_controls = coordinator.data.get_temperature_controls()
            if (
                (tc := temp_controls.get(zone_id))
                and isinstance(tc.zone_position, ZonePosition)
                and (zone_key := ZONE_POSITION_MAP.get(tc.zone_position))
            ):
                self._attr_translation_key = f"{description.translation_key}_{zone_key}"

    @property
    def _select_control(self) -> SelectControl | None:
        """Get the select control for this entity."""
        for control in self.coordinator.data.controls:
            if not isinstance(
                control,
                IceMakerControl | HydroBreezeControl | BioFreshPlusControl,
            ):
                continue
            if (
                isinstance(control, self.entity_description.control_type)
                and control.zone_id == self._zone_id
            ):
                return control
        return None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        control = self._select_control
        if TYPE_CHECKING:
            assert isinstance(
                control,
                IceMakerControl | HydroBreezeControl | BioFreshPlusControl,
            )
        mode = self.entity_description.current_mode_fn(control)
        if isinstance(mode, StrEnum):
            return mode.value
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._select_control is not None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = self.entity_description.mode_enum(option)
        await self._async_send_command(
            self.entity_description.set_fn(self.coordinator, self._zone_id, mode),
        )
