"""The Aprilaire select component."""

from __future__ import annotations

from pyaprilaire.const import Attribute

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AprilaireCoordinator
from .entity import BaseAprilaireEntity

AIR_CLEANING_EVENT_MAP = {0: "off", 3: "event_clean", 4: "allergies"}
AIR_CLEANING_MODE_MAP = {0: "off", 1: "constant_clean", 2: "automatic"}
FRESH_AIR_EVENT_MAP = {0: "off", 2: "3hour", 3: "24hour"}
FRESH_AIR_MODE_MAP = {0: "off", 1: "automatic"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aprilaire select devices."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.unique_id]

    assert config_entry.unique_id is not None

    entities: list[SelectEntity] = []

    if coordinator.data.get(Attribute.AIR_CLEANING_AVAILABLE) == 1:
        entities.append(
            AprilaireAirCleaningEventEntity(coordinator, config_entry.unique_id)
        )

        entities.append(
            AprilaireAirCleaningModeEntity(coordinator, config_entry.unique_id)
        )

    if coordinator.data.get(Attribute.VENTILATION_AVAILABLE) == 1:
        entities.append(
            AprilaireFreshAirEventEntity(coordinator, config_entry.unique_id)
        )

        entities.append(
            AprilaireFreshAirModeEntity(coordinator, config_entry.unique_id)
        )

    async_add_entities(entities)


class AprilaireAirCleaningEventEntity(BaseAprilaireEntity, SelectEntity):
    """Aprilaire air cleaning event entity."""

    _attr_translation_key = "air_cleaning_event"

    def __init__(self, coordinator: AprilaireCoordinator, unique_id: str) -> None:
        """Initialize an Aprilaire air cleaning event entity."""

        super().__init__(coordinator, unique_id)

        self._attr_options = list(set(AIR_CLEANING_EVENT_MAP.values()))

    @property
    def current_option(self) -> str:
        """Get the current air cleaning event."""

        air_cleaning_event = int(
            self.coordinator.data.get(Attribute.AIR_CLEANING_EVENT, 0)
        )

        return AIR_CLEANING_EVENT_MAP.get(air_cleaning_event, "off")

    async def async_select_option(self, option: str) -> None:
        """Set the air cleaning event."""

        current_air_cleaning_mode = self.coordinator.data.get(
            Attribute.AIR_CLEANING_MODE, 0
        )

        air_cleaning_event_value = next(
            key for key, value in AIR_CLEANING_EVENT_MAP.items() if value == option
        )

        await self.coordinator.client.set_air_cleaning(
            current_air_cleaning_mode, air_cleaning_event_value
        )


class AprilaireAirCleaningModeEntity(BaseAprilaireEntity, SelectEntity):
    """Aprilaire air cleaning mode entity."""

    _attr_translation_key = "air_cleaning_mode"

    def __init__(self, coordinator: AprilaireCoordinator, unique_id: str) -> None:
        """Initialize an Aprilaire air cleaning mode entity."""

        super().__init__(coordinator, unique_id)

        self._attr_options = list(set(AIR_CLEANING_MODE_MAP.values()))

    @property
    def current_option(self) -> str:
        """Get the current air cleaning mode."""

        air_cleaning_mode = int(
            self.coordinator.data.get(Attribute.AIR_CLEANING_MODE, 0)
        )

        return AIR_CLEANING_MODE_MAP.get(air_cleaning_mode, "off")

    async def async_select_option(self, option: str) -> None:
        """Set the air cleaning mode."""

        current_air_cleaning_event = self.coordinator.data.get(
            Attribute.AIR_CLEANING_EVENT, 0
        )

        air_cleaning_mode_value = next(
            key for key, value in AIR_CLEANING_MODE_MAP.items() if value == option
        )

        await self.coordinator.client.set_air_cleaning(
            air_cleaning_mode_value, current_air_cleaning_event
        )


class AprilaireFreshAirEventEntity(BaseAprilaireEntity, SelectEntity):
    """Aprilaire fresh air event entity."""

    _attr_translation_key = "fresh_air_event"

    def __init__(self, coordinator: AprilaireCoordinator, unique_id: str) -> None:
        """Initialize an Aprilaire fresh air event entity."""

        super().__init__(coordinator, unique_id)

        self._attr_options = list(set(FRESH_AIR_EVENT_MAP.values()))

    @property
    def current_option(self) -> str:
        """Get the current fresh air event."""

        fresh_air_event = int(self.coordinator.data.get(Attribute.FRESH_AIR_EVENT, 0))

        return FRESH_AIR_EVENT_MAP.get(fresh_air_event, "off")

    async def async_select_option(self, option: str) -> None:
        """Set the fresh air event."""

        current_fresh_air_mode = self.coordinator.data.get(Attribute.FRESH_AIR_MODE, 0)

        fresh_air_event_value = next(
            key for key, value in FRESH_AIR_EVENT_MAP.items() if value == option
        )

        await self.coordinator.client.set_fresh_air(
            current_fresh_air_mode, fresh_air_event_value
        )


class AprilaireFreshAirModeEntity(BaseAprilaireEntity, SelectEntity):
    """Aprilaire fresh air mode entity."""

    _attr_translation_key = "fresh_air_mode"

    def __init__(self, coordinator: AprilaireCoordinator, unique_id: str) -> None:
        """Initialize an Aprilaire fresh air mode entity."""

        super().__init__(coordinator, unique_id)

        self._attr_options = list(set(FRESH_AIR_MODE_MAP.values()))

    @property
    def current_option(self) -> str:
        """Get the current fresh air mode."""

        fresh_air_mode = int(self.coordinator.data.get(Attribute.FRESH_AIR_MODE, 0))

        return FRESH_AIR_MODE_MAP.get(fresh_air_mode, "off")

    async def async_select_option(self, option: str) -> None:
        """Set the fresh air mode."""

        current_fresh_air_event = self.coordinator.data.get(
            Attribute.AIR_CLEANING_EVENT, 0
        )

        fresh_air_mode_value = next(
            key for key, value in FRESH_AIR_MODE_MAP.items() if value == option
        )

        await self.coordinator.client.set_fresh_air(
            fresh_air_mode_value, current_fresh_air_event
        )
