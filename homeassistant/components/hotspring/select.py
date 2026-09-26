"""Support for Hot Spring select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast, override

from hotspring import HeatingMode, HotSpring, Jet, JetSpeed, Spa

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
class HotSpringJetSelectEntityDescription(SelectEntityDescription):
    """Class describing Hot Spring jet select entities."""

    current_option_fn: Callable[[Jet], str | None]
    select_option_fn: Callable[[HotSpring, int, str], Awaitable[None]]
    options_fn: Callable[[Jet], list[str]]
    exists_fn: Callable[[Jet], bool] = lambda jet: jet.is_enabled


@dataclass(frozen=True, kw_only=True)
class HotSpringHeatingModeSelectEntityDescription(SelectEntityDescription):
    """Class describing Hot Spring heating mode select entities."""

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


JET_DESCRIPTIONS: tuple[HotSpringJetSelectEntityDescription, ...] = (
    HotSpringJetSelectEntityDescription(
        key="jet",
        translation_key="jet",
        options_fn=lambda jet: (
            DUAL_SPEED_OPTIONS if jet.is_dual_speed else SINGLE_SPEED_OPTIONS
        ),
        current_option_fn=lambda jet: JET_SPEED_TO_OPTION.get(jet.speed),
        select_option_fn=lambda hotspring, jet_id, option: hotspring.set_jet(
            jet_id, OPTION_TO_JET_SPEED[option]
        ),
    ),
)

HEATING_MODE_DESCRIPTIONS: tuple[HotSpringHeatingModeSelectEntityDescription, ...] = (
    HotSpringHeatingModeSelectEntityDescription(
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring select entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        HotSpringJetSelectEntity(coordinator, description, jet.jet_id)
        for description in JET_DESCRIPTIONS
        for jet in coordinator.data.jets.values()
        if description.exists_fn(jet)
    )
    async_add_entities(
        HotSpringHeatingModeSelectEntity(coordinator, description)
        for description in HEATING_MODE_DESCRIPTIONS
        if description.exists_fn(coordinator.data)
    )


class HotSpringJetSelectEntity(HotSpringEntity, SelectEntity):
    """Defines a Hot Spring jet select entity."""

    entity_description: HotSpringJetSelectEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: HotSpringJetSelectEntityDescription,
        jet_id: int,
    ) -> None:
        """Initialize the jet select entity."""
        super().__init__(coordinator, f"{description.key}_{jet_id}")
        self.entity_description = description
        self._jet_id = jet_id
        self._attr_translation_placeholders = {"jet": str(jet_id)}

    @property
    def _jet(self) -> Jet:
        """Return the jet data."""
        return self.coordinator.data.jets[self._jet_id]

    @property
    @override
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options_fn(self._jet)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current select option."""
        return self.entity_description.current_option_fn(self._jet)

    @hotspring_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_option_fn(
            self.coordinator.hotspring, self._jet_id, option
        )
        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )


class HotSpringHeatingModeSelectEntity(HotSpringEntity, SelectEntity):
    """Defines a Hot Spring heating mode select entity."""

    entity_description: HotSpringHeatingModeSelectEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: HotSpringHeatingModeSelectEntityDescription,
    ) -> None:
        """Initialize the heating mode select entity."""
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
