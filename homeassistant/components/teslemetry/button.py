"""Button platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.components.labs import async_is_preview_feature_enabled
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslemetryConfigEntry
from .const import DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE
from .entity import TeslemetryVehicleStreamEntity
from .helpers import handle_command, handle_vehicle_command
from .models import TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryButtonEntityDescription(ButtonEntityDescription):
    """Describes a Teslemetry Button entity."""

    func: Callable[[TeslemetryButtonEntity], Awaitable[Any]]


DESCRIPTIONS: tuple[TeslemetryButtonEntityDescription, ...] = (
    TeslemetryButtonEntityDescription(
        key="wake", func=lambda self: handle_command(self.api.wake_up())
    ),
    TeslemetryButtonEntityDescription(
        key="flash_lights",
        func=lambda self: handle_vehicle_command(self.api.flash_lights()),
    ),
    TeslemetryButtonEntityDescription(
        key="honk", func=lambda self: handle_vehicle_command(self.api.honk_horn())
    ),
    TeslemetryButtonEntityDescription(
        key="enable_keyless_driving",
        func=lambda self: handle_vehicle_command(self.api.remote_start_drive()),
    ),
    TeslemetryButtonEntityDescription(
        key="boombox",
        func=lambda self: handle_vehicle_command(self.api.remote_boombox(0)),
    ),
    TeslemetryButtonEntityDescription(
        key="homelink",
        func=lambda self: handle_vehicle_command(
            self.api.trigger_homelink(
                lat=self.hass.config.latitude,
                lon=self.hass.config.longitude,
            )
        ),
    ),
)

CHARGE_ON_SOLAR_DESCRIPTIONS: tuple[TeslemetryButtonEntityDescription, ...] = (
    TeslemetryButtonEntityDescription(
        key="enable_charge_on_solar",
        func=lambda self: handle_vehicle_command(
            self.api.charge_on_solar(enabled=True)
        ),
    ),
    TeslemetryButtonEntityDescription(
        key="disable_charge_on_solar",
        func=lambda self: handle_vehicle_command(
            self.api.charge_on_solar(enabled=False)
        ),
    ),
)


def _async_remove_charge_on_solar_buttons(
    hass: HomeAssistant, entry: TeslemetryConfigEntry
) -> None:
    """Remove stale charge-on-solar button entities when preview is disabled."""
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.domain == BUTTON_DOMAIN and entity_entry.translation_key in {
            "enable_charge_on_solar",
            "disable_charge_on_solar",
        }:
            entity_registry.async_remove(entity_entry.entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Button platform from a config entry."""

    descriptions = DESCRIPTIONS
    if async_is_preview_feature_enabled(hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE):
        descriptions += CHARGE_ON_SOLAR_DESCRIPTIONS
    else:
        _async_remove_charge_on_solar_buttons(hass, entry)

    async_add_entities(
        TeslemetryButtonEntity(vehicle, description)
        for vehicle in entry.runtime_data.vehicles
        for description in descriptions
        if Scope.VEHICLE_CMDS in entry.runtime_data.scopes
    )


class TeslemetryButtonEntity(TeslemetryVehicleStreamEntity, ButtonEntity):
    """Base class for Teslemetry buttons."""

    api: Vehicle
    entity_description: TeslemetryButtonEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.func(self)
