"""Support for SleepIQ foundation preset selection."""

from __future__ import annotations

from asyncsleepiq import (
    CoreTemps,
    FootWarmingTemps,
    Side,
    SleepIQBed,
    SleepIQCoreClimate,
    SleepIQFootWarmer,
    SleepIQPreset,
)

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CORE_CLIMATE, DOMAIN, FOOT_WARMER
from .coordinator import SleepIQData, SleepIQDataUpdateCoordinator
from .entity import SleepIQBedEntity, SleepIQSleeperEntity, sleeper_for_side


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ foundation preset select entities."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SleepIQBedEntity] = []
    for bed in data.client.beds.values():
        entities.extend(
            SleepIQSelectEntity(data.data_coordinator, bed, preset)
            for preset in bed.foundation.presets
        )
        entities.extend(
            SleepIQFootWarmingTempSelectEntity(data.data_coordinator, bed, foot_warmer)
            for foot_warmer in bed.foundation.foot_warmers
        )
        entities.extend(
            SleepIQCoreTempSelectEntity(data.data_coordinator, bed, core_climate)
            for core_climate in bed.foundation.core_climates
        )
    async_add_entities(entities)


class SleepIQSelectEntity(SleepIQBedEntity[SleepIQDataUpdateCoordinator], SelectEntity):
    """Representation of a SleepIQ select entity."""

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        preset: SleepIQPreset,
    ) -> None:
        """Initialize the select entity."""
        self.preset = preset

        self._attr_name = f"SleepNumber {bed.name} Foundation Preset"
        self._attr_unique_id = f"{bed.id}_preset"
        if preset.side != Side.NONE:
            self._attr_name += f" {preset.side_full}"
            self._attr_unique_id += f"_{preset.side.value}"
        self._attr_options = preset.options

        super().__init__(coordinator, bed)
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_current_option = self.preset.preset

    async def async_select_option(self, option: str) -> None:
        """Change the current preset."""
        await self.preset.set_preset(option)
        self._attr_current_option = option
        self.async_write_ha_state()


class SleepIQFootWarmingTempSelectEntity(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator], SelectEntity
):
    """Representation of a SleepIQ foot warming temperature select entity."""

    _attr_icon = "mdi:heat-wave"
    _attr_options = [e.name.lower() for e in FootWarmingTemps]
    _attr_translation_key = "foot_warmer_temp"

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        foot_warmer: SleepIQFootWarmer,
    ) -> None:
        """Initialize the select entity."""
        self.foot_warmer = foot_warmer
        sleeper = sleeper_for_side(bed, foot_warmer.side)
        super().__init__(coordinator, bed, sleeper, FOOT_WARMER)
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._attr_current_option = FootWarmingTemps(
            self.foot_warmer.temperature
        ).name.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the current preset."""
        temperature = FootWarmingTemps[option.upper()]
        timer = self.foot_warmer.timer or 120

        if temperature == 0:
            await self.foot_warmer.turn_off()
        else:
            await self.foot_warmer.turn_on(temperature, timer)

        self._attr_current_option = option
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


class SleepIQCoreTempSelectEntity(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator], SelectEntity
):
    """Representation of a SleepIQ core climate temperature select entity."""

    # Maps to translate between asyncsleepiq and HA's naming preference
    SLEEPIQ_TO_HA_CORE_TEMP_MAP = {
        CoreTemps.OFF: "off",
        CoreTemps.HEATING_PUSH_LOW: "heating_low",
        CoreTemps.HEATING_PUSH_MED: "heating_medium",
        CoreTemps.HEATING_PUSH_HIGH: "heating_high",
        CoreTemps.COOLING_PULL_LOW: "cooling_low",
        CoreTemps.COOLING_PULL_MED: "cooling_medium",
        CoreTemps.COOLING_PULL_HIGH: "cooling_high",
    }
    HA_TO_SLEEPIQ_CORE_TEMP_MAP = {v: k for k, v in SLEEPIQ_TO_HA_CORE_TEMP_MAP.items()}

    _attr_icon = "mdi:heat-wave"
    _attr_options = list(SLEEPIQ_TO_HA_CORE_TEMP_MAP.values())
    _attr_translation_key = "core_temps"

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        core_climate: SleepIQCoreClimate,
    ) -> None:
        """Initialize the select entity."""
        self.core_climate = core_climate
        sleeper = sleeper_for_side(bed, core_climate.side)
        super().__init__(coordinator, bed, sleeper, CORE_CLIMATE)
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        sleepiq_option = CoreTemps(self.core_climate.temperature)
        self._attr_current_option = self.SLEEPIQ_TO_HA_CORE_TEMP_MAP[sleepiq_option]

    async def async_select_option(self, option: str) -> None:
        """Change the current preset."""
        temperature = self.HA_TO_SLEEPIQ_CORE_TEMP_MAP[option]
        timer = self.core_climate.timer or 240

        if temperature == CoreTemps.OFF:
            await self.core_climate.turn_off()
        else:
            await self.core_climate.turn_on(temperature, timer)

        self._attr_current_option = option
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
