"""Support for Hot Spring select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast, override

from hotspring import HeatingMode, HotSpring, JetSpeed, Spa

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity
from .helpers import hotspring_exception_handler

PARALLEL_UPDATES = 1

OPTION_OFF = "off"
OPTION_LOW = "low"
OPTION_HIGH = "high"

JET_SPEED_TO_OPTION: dict[JetSpeed, str] = {
    JetSpeed.OFF: OPTION_OFF,
    JetSpeed.LOW_SPEED: OPTION_LOW,
    JetSpeed.HIGH_SPEED: OPTION_HIGH,
}

OPTION_TO_JET_SPEED: dict[str, JetSpeed] = {
    OPTION_OFF: JetSpeed.OFF,
    OPTION_LOW: JetSpeed.LOW_SPEED,
    OPTION_HIGH: JetSpeed.HIGH_SPEED,
}

DUAL_SPEED_OPTIONS = [OPTION_OFF, OPTION_LOW, OPTION_HIGH]
SINGLE_SPEED_OPTIONS = [OPTION_OFF, OPTION_HIGH]

OPTION_HEAT_SAVER = "heat_saver"
OPTION_HEAT_WITH_BOOST = "heat_with_boost"
OPTION_AUTO_SAVER = "auto_saver"
OPTION_AUTO_WITH_BOOST = "auto_with_boost"
OPTION_CHILL = "chill"

HEATING_MODE_TO_OPTION: dict[HeatingMode, str] = {
    HeatingMode.HEAT_SAVER: OPTION_HEAT_SAVER,
    HeatingMode.HEAT_WITH_BOOST: OPTION_HEAT_WITH_BOOST,
    HeatingMode.AUTO_SAVER: OPTION_AUTO_SAVER,
    HeatingMode.AUTO_WITH_BOOST: OPTION_AUTO_WITH_BOOST,
    HeatingMode.CHILL: OPTION_CHILL,
}

OPTION_TO_HEATING_MODE: dict[str, HeatingMode] = {
    OPTION_HEAT_SAVER: HeatingMode.HEAT_SAVER,
    OPTION_HEAT_WITH_BOOST: HeatingMode.HEAT_WITH_BOOST,
    OPTION_AUTO_SAVER: HeatingMode.AUTO_SAVER,
    OPTION_AUTO_WITH_BOOST: HeatingMode.AUTO_WITH_BOOST,
    OPTION_CHILL: HeatingMode.CHILL,
}


@dataclass(frozen=True, kw_only=True)
class HotSpringSelectEntityDescription(SelectEntityDescription):
    """Class describing Hot Spring select entities."""

    current_option_fn: Callable[[Spa], str | None]
    select_option_fn: Callable[[HotSpring, str], Awaitable[None]]
    options_fn: Callable[[Spa], list[str]]
    exists_fn: Callable[[Spa], bool] = lambda _: True


def _heating_mode_options(spa: Spa) -> list[str]:
    """Return available heating mode options."""
    options = [
        OPTION_HEAT_SAVER,
        OPTION_HEAT_WITH_BOOST,
        OPTION_AUTO_SAVER,
        OPTION_AUTO_WITH_BOOST,
    ]
    if spa.heater.heatpump_installed:
        options.append(OPTION_CHILL)
    return options


ENTITY_DESCRIPTIONS: tuple[HotSpringSelectEntityDescription, ...] = (
    HotSpringSelectEntityDescription(
        key="heating_mode",
        translation_key="heating_mode",
        entity_category=EntityCategory.CONFIG,
        exists_fn=lambda spa: spa.heater.heating_mode in HEATING_MODE_TO_OPTION,
        options_fn=_heating_mode_options,
        current_option_fn=lambda spa: HEATING_MODE_TO_OPTION.get(
            spa.heater.heating_mode
        ),
        select_option_fn=lambda hotspring, option: hotspring.set_heating_mode(
            OPTION_TO_HEATING_MODE[option]
        ),
    ),
)


def _get_jet_description(jet_id: int) -> HotSpringSelectEntityDescription:
    """Return a select entity description for a jet pump."""
    return HotSpringSelectEntityDescription(
        key=f"jet_{jet_id}",
        translation_key="jet",
        translation_placeholders={"jet": str(jet_id)},
        options_fn=lambda spa: (
            DUAL_SPEED_OPTIONS
            if spa.jets[jet_id].is_dual_speed
            else SINGLE_SPEED_OPTIONS
        ),
        current_option_fn=lambda spa: JET_SPEED_TO_OPTION.get(spa.jets[jet_id].speed),
        select_option_fn=lambda hotspring, option: hotspring.set_jet(
            jet_id, OPTION_TO_JET_SPEED[option]
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring select entities."""
    coordinator = entry.runtime_data
    entities: list[HotSpringSelectEntity] = [
        HotSpringSelectEntity(coordinator, _get_jet_description(jet.jet_id))
        for jet in coordinator.data.jets.values()
        if jet.is_enabled
    ]
    entities.extend(
        HotSpringSelectEntity(coordinator, description)
        for description in ENTITY_DESCRIPTIONS
        if description.exists_fn(coordinator.data)
    )
    async_add_entities(entities)


class HotSpringSelectEntity(HotSpringEntity, SelectEntity):
    """Defines a Hot Spring select entity."""

    entity_description: HotSpringSelectEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: HotSpringSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options_fn(self.coordinator.data)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current select option."""
        return self.entity_description.current_option_fn(self.coordinator.data)

    @hotspring_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_option_fn(
            self.coordinator.hotspring, option
        )
        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )
