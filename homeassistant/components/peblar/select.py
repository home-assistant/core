"""Support for Peblar selects."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from peblar import Peblar, PeblarUserConfiguration, SmartChargingMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PeblarConfigEntry, PeblarUserConfigurationDataUpdateCoordinator
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarSelectEntityDescription(SelectEntityDescription):
    """Class describing Peblar select entities."""

    options_fn: Callable[[PeblarUserConfiguration], list[str]] | None = None
    current_fn: Callable[[PeblarUserConfiguration], str | None]
    select_fn: Callable[[Peblar, str], Awaitable[Any]]


def _smart_charging_options(configuration: PeblarUserConfiguration) -> list[str]:
    """Return the smart charging modes this charger will accept.

    A charger without a power meter configured rejects solar charging, and
    scheduled charging can be switched off during commissioning. Offering
    those anyway lands the user on a mode the charger quietly ignores.
    """
    solar = configuration.solar_charging_allowed
    return [
        option
        for option, allowed in (
            ("default", True),
            ("fast_solar", solar),
            ("pure_solar", solar),
            ("scheduled", configuration.scheduled_charging_allowed),
            ("smart_solar", solar),
        )
        if allowed
    ]


DESCRIPTIONS = [
    PeblarSelectEntityDescription(
        key="smart_charging",
        translation_key="smart_charging",
        entity_category=EntityCategory.CONFIG,
        options_fn=_smart_charging_options,
        current_fn=lambda x: x.smart_charging.value if x.smart_charging else None,
        select_fn=lambda x, mode: x.smart_charging(SmartChargingMode(mode)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar select based on a config entry."""
    async_add_entities(
        PeblarSelectEntity(
            entry=entry,
            coordinator=entry.runtime_data.user_configuration_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
    )


class PeblarSelectEntity(
    PeblarEntity[PeblarUserConfigurationDataUpdateCoordinator],
    SelectEntity,
):
    """Defines a Peblar select entity."""

    entity_description: PeblarSelectEntityDescription

    @property
    @override
    def options(self) -> list[str]:
        """Return the options this charger currently accepts."""
        if (options_fn := self.entity_description.options_fn) is not None:
            return options_fn(self.coordinator.data)
        return super().options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @peblar_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.peblar, option)
        await self.coordinator.async_request_refresh()
