"""Support for Hot Spring select entities."""

from typing import cast, override

from hotspring import HeatingMode, Jet, JetSpeed, Spa

from homeassistant.components.select import SelectEntity
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring select entities."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        HotSpringJetSelectEntity(coordinator, jet.jet_id)
        for jet in coordinator.data.jets.values()
        if jet.is_enabled
    ]
    if coordinator.data.heater.heating_mode in HEATING_MODE_TO_OPTION:
        entities.append(HotSpringHeatingModeSelectEntity(coordinator))

    async_add_entities(entities)


class HotSpringJetSelectEntity(HotSpringEntity, SelectEntity):
    """Defines a Hot Spring jet select entity."""

    _attr_translation_key = "jet"

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        jet_id: int,
    ) -> None:
        """Initialize the jet select entity."""
        super().__init__(coordinator, f"jet_{jet_id}")
        self._jet_id = jet_id
        self._attr_translation_placeholders = {"jet": str(jet_id)}
        self._attr_options = (
            DUAL_SPEED_OPTIONS if self._jet.is_dual_speed else SINGLE_SPEED_OPTIONS
        )

    @property
    def _jet(self) -> Jet:
        """Return the jet data."""
        return self.coordinator.data.jets[self._jet_id]

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current jet speed option."""
        return JET_SPEED_TO_OPTION.get(self._jet.speed)

    @hotspring_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected jet speed."""
        await self.coordinator.hotspring.set_jet(
            self._jet_id, OPTION_TO_JET_SPEED[option]
        )
        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )


class HotSpringHeatingModeSelectEntity(HotSpringEntity, SelectEntity):
    """Defines a Hot Spring heating mode select entity."""

    _attr_translation_key = "heating_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
    ) -> None:
        """Initialize the heating mode select entity."""
        super().__init__(coordinator, "heating_mode")
        options = [
            OPTION_HEAT_SAVER,
            OPTION_HEAT_WITH_BOOST,
            OPTION_AUTO_SAVER,
            OPTION_AUTO_WITH_BOOST,
        ]
        if coordinator.data.heater.heatpump_installed:
            options.append(OPTION_CHILL)
        self._attr_options = options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current heating mode."""
        return HEATING_MODE_TO_OPTION.get(self.coordinator.data.heater.heating_mode)

    @hotspring_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the heating mode."""
        await self.coordinator.hotspring.set_heating_mode(
            OPTION_TO_HEATING_MODE[option]
        )
        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )
