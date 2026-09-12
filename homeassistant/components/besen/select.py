"""Select platform for Besen."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final, override

from besen.models import BesenData

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenConfigEntry
from .coordinator import BesenCoordinator
from .entity import BesenEntity

PARALLEL_UPDATES = 0

LANGUAGE_OPTIONS: Final = {
    "english": "English",
    "italian": "Italiano",
    "german": "Deutsch",
    "french": "Fran\u00e7ais",
    "spanish": "Espa\u00f1ol",
    "hebrew": "\u05e2\u05d1\u05e8\u05d9\u05ea",
    "polish": "Polski",
    "chinese": "\u4e2d\u6587",
}
LANGUAGE_VALUES: Final = {value: key for key, value in LANGUAGE_OPTIONS.items()}

TEMPERATURE_UNIT_OPTIONS: Final = {
    "celsius": "Celsius",
    "fahrenheit": "Fahrenheit",
}
TEMPERATURE_UNIT_VALUES: Final = {
    value: key for key, value in TEMPERATURE_UNIT_OPTIONS.items()
}


def _option_value(value: str | None, options: Mapping[str, str]) -> str | None:
    """Return a Home Assistant option for a charger value."""

    return options.get(value) if value is not None else None


@dataclass(frozen=True, kw_only=True)
class BesenSelectEntityDescription(SelectEntityDescription):
    """Describe a Besen select entity."""

    current_option_fn: Callable[[BesenData], str | None]
    option_values: dict[str, str]
    select_option_fn: Callable[[BesenCoordinator, str], Awaitable[None]]


SELECT_DESCRIPTIONS: tuple[BesenSelectEntityDescription, ...] = (
    BesenSelectEntityDescription(
        key="language",
        translation_key="language",
        entity_category=EntityCategory.CONFIG,
        options=list(LANGUAGE_OPTIONS),
        current_option_fn=lambda data: _option_value(
            data.config.language, LANGUAGE_VALUES
        ),
        option_values=LANGUAGE_OPTIONS,
        select_option_fn=lambda coordinator, option: coordinator.async_set_language(
            option
        ),
    ),
    BesenSelectEntityDescription(
        key="temperature_unit",
        translation_key="temperature_unit",
        entity_category=EntityCategory.CONFIG,
        options=list(TEMPERATURE_UNIT_OPTIONS),
        current_option_fn=lambda data: _option_value(
            data.config.temperature_unit, TEMPERATURE_UNIT_VALUES
        ),
        option_values=TEMPERATURE_UNIT_OPTIONS,
        select_option_fn=lambda coordinator, option: (
            coordinator.async_set_temperature_unit(option)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Besen select platform."""

    async_add_entities(
        BesenSelect(entry.runtime_data, description)
        for description in SELECT_DESCRIPTIONS
    )


class BesenSelect(BesenEntity, SelectEntity):
    """Representation of a Besen select."""

    entity_description: BesenSelectEntityDescription

    def __init__(
        self,
        coordinator: BesenCoordinator,
        description: BesenSelectEntityDescription,
    ) -> None:
        """Initialize a Besen select."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""

        return self.entity_description.current_option_fn(self.coordinator.data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""

        await self.entity_description.select_option_fn(
            self.coordinator,
            self.entity_description.option_values[option],
        )
