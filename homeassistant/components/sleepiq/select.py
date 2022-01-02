"""Support for selecting a SleepNumber foundation preset position."""

from typing import List

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_SLEEPIQ, SleepIQDataUpdateCoordinator, SleepIQEntity
from .const import (
    ATTRIBUTES,
    NAME,
    NOT_AT_PRESET,
    PRESET,
    PRESETS,
    RIGHT,
    SENSOR_TYPES,
    SIDES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator = hass.data[DATA_SLEEPIQ].coordinators[config_entry.data[CONF_USERNAME]]
    entities = []

    for bed_id in coordinator.data:
        foundation_features = await hass.async_add_executor_job(
            coordinator.client.foundation_features, bed_id
        )

        if foundation_features.single:
            entities.append(
                SleepIQFoundationPresetSelect(
                    coordinator, bed_id, RIGHT, foundation_features.single
                )
            )
        else:
            for side in SIDES:
                entities.append(
                    SleepIQFoundationPresetSelect(
                        coordinator, bed_id, side, foundation_features.single
                    )
                )

    async_add_entities(entities, True)


class SleepIQFoundationPresetSelect(SleepIQEntity, SelectEntity):
    """Implementation of a foundation preset select entity."""

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
        single: bool,
    ) -> None:
        """Initialize the SleepIQ foundation preset select entity."""
        super().__init__(coordinator, bed_id, side)
        self.client = coordinator.client
        self.single = single

    async def async_select_option(self, option: str) -> None:
        """Select a foundation preset."""
        if option != NOT_AT_PRESET:
            await self.hass.async_add_executor_job(
                self.client.preset, PRESETS[option], self.side, self.bed_id
            )
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def options(self) -> List:
        """Return the list of possible options."""
        return list(PRESETS)

    @property
    def current_option(self) -> str:
        """Return the current foundation preset."""
        return getattr(self._foundation, ATTRIBUTES[self.side][PRESET])

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        unique_id = f"{self.bed_id}_{self._side.sleeper.first_name}"
        if not self.single:
            unique_id += f"_{self.side}"
        return f"{unique_id}_{PRESET}"

    @property
    def name(self) -> str:
        """Return name for the entity."""
        name = f"{NAME} {self._bed.name}"
        if not self.single:
            name += f" {self._side.sleeper.first_name}"
        return f"{name} {SENSOR_TYPES[PRESET]}"
