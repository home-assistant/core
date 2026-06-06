"""Climate platform for MELCloud Home."""

from typing import Any

from aiomelcloudhome import ATAFanSpeed, ATAOperationMode, ATAUnit, ATWUnit, ATWZoneMode

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudHomeConfigEntry, MelCloudHomeCoordinator
from .entity import MelCloudHomeATAUnitEntity, MelCloudHomeATWZoneEntity

ATA_HVAC_MODE_TO_OPERATION: dict[HVACMode, ATAOperationMode] = {
    HVACMode.HEAT: ATAOperationMode.HEAT,
    HVACMode.COOL: ATAOperationMode.COOL,
    HVACMode.AUTO: ATAOperationMode.AUTOMATIC,
    HVACMode.DRY: ATAOperationMode.DRY,
    HVACMode.FAN_ONLY: ATAOperationMode.FAN,
}

ATA_OPERATION_TO_HVAC_MODE: dict[ATAOperationMode, HVACMode] = {
    value: key for key, value in ATA_HVAC_MODE_TO_OPERATION.items()
}

ATA_FAN_SPEED_TO_HA: dict[ATAFanSpeed, str] = {
    ATAFanSpeed.AUTO: "auto",
    ATAFanSpeed.ONE: "1",
    ATAFanSpeed.TWO: "2",
    ATAFanSpeed.THREE: "3",
    ATAFanSpeed.FOUR: "4",
    ATAFanSpeed.FIVE: "5",
}

HA_FAN_SPEED_TO_ATA: dict[str, ATAFanSpeed] = {
    value: key for key, value in ATA_FAN_SPEED_TO_HA.items()
}

ATW_ZONE_MODE_TO_HVAC_MODE: dict[ATWZoneMode, HVACMode] = {
    ATWZoneMode.HEAT_ROOM_TEMPERATURE: HVACMode.HEAT,
    ATWZoneMode.HEAT_FLOW_TEMPERATURE: HVACMode.HEAT,
    ATWZoneMode.HEAT_CURVE: HVACMode.HEAT,
    ATWZoneMode.COOL_ROOM_TEMPERATURE: HVACMode.COOL,
    ATWZoneMode.COOL_FLOW_TEMPERATURE: HVACMode.COOL,
}

HVAC_MODE_TO_ATW_ZONE_MODE: dict[HVACMode, ATWZoneMode] = {
    HVACMode.HEAT: ATWZoneMode.HEAT_ROOM_TEMPERATURE,
    HVACMode.COOL: ATWZoneMode.COOL_ROOM_TEMPERATURE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MELCloud Home climate entities from a config entry."""
    coordinator = entry.runtime_data.coordinator

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(ATAClimateEntity(coordinator, unit) for unit in units)

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        # Erwin: create zone 1 for all units, and zone 2 only when the unit supports it.
        async_add_entities(
            ATWZoneClimateEntity(coordinator, unit, zone_number=zone_number)
            for unit in units
            for zone_number in (
                [1, 2]
                if (unit.capabilities and unit.capabilities.has_zone2)
                or (unit.capabilities is None and unit.has_zone2)
                else [1]
            )
        )

    coordinator.new_ata_callbacks.append(_async_add_new_ata_units)
    coordinator.new_atw_callbacks.append(_async_add_new_atw_units)

    _async_add_new_ata_units(
        [
            unit
            for building in coordinator.data.buildings
            for unit in building.air_to_air_units
        ]
    )
    _async_add_new_atw_units(
        [
            unit
            for building in coordinator.data.buildings
            for unit in building.air_to_water_units
        ]
    )


class ATAClimateEntity(MelCloudHomeATAUnitEntity, ClimateEntity):
    """Climate entity for a MELCloud Home Air-to-Air unit."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = list(ATA_FAN_SPEED_TO_HA.values())
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        unit = self.unit
        return unit.room_temperature if unit else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        unit = self.unit
        return unit.set_temperature if unit else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        unit = self.unit
        if unit is None or not unit.power:
            return HVACMode.OFF
        if unit.operation_mode is None:
            return HVACMode.OFF
        return ATA_OPERATION_TO_HVAC_MODE.get(unit.operation_mode, HVACMode.OFF)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        unit = self.unit
        if unit is None or unit.set_fan_speed is None:
            return None
        return ATA_FAN_SPEED_TO_HA.get(unit.set_fan_speed)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.control_ata_unit(self._unit_id, power=False)
        else:
            await self.coordinator.client.control_ata_unit(
                self._unit_id,
                power=True,
                operation_mode=ATA_HVAC_MODE_TO_OPERATION[hvac_mode],
            )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.client.control_ata_unit(
            self._unit_id, set_temperature=temperature
        )
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if (ata_fan_speed := HA_FAN_SPEED_TO_ATA.get(fan_mode)) is None:
            return
        await self.coordinator.client.control_ata_unit(
            self._unit_id, set_fan_speed=ata_fan_speed
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the unit on."""
        await self.coordinator.client.control_ata_unit(self._unit_id, power=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the unit off."""
        await self.coordinator.client.control_ata_unit(self._unit_id, power=False)
        await self.coordinator.async_request_refresh()


class ATWZoneClimateEntity(MelCloudHomeATWZoneEntity, ClimateEntity):
    """Climate entity for a MELCloud Home ATW zone."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: MelCloudHomeCoordinator,
        unit: ATWUnit,
        zone_number: int,
    ) -> None:
        """Initialize the ATW zone climate entity."""
        super().__init__(coordinator, unit, zone_number)
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if unit.capabilities is None or unit.capabilities.has_cooling_mode:
            self._attr_hvac_modes.append(HVACMode.COOL)

    @property
    def _zone_mode(self) -> ATWZoneMode | None:
        """Return the current ATW zone mode."""
        unit = self.unit
        if unit is None:
            return None
        if self.zone_number == 1:
            return unit.operation_mode_zone1
        return unit.operation_mode_zone2

    @property
    def current_temperature(self) -> float | None:
        """Return the current zone temperature."""
        unit = self.unit
        if unit is None:
            return None
        return (
            unit.room_temperature_zone1
            if self.zone_number == 1
            else unit.room_temperature_zone2
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the target zone temperature."""
        unit = self.unit
        if unit is None:
            return None
        return (
            unit.set_temperature_zone1
            if self.zone_number == 1
            else unit.set_temperature_zone2
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        unit = self.unit
        if unit is None or not unit.power:
            return HVACMode.OFF

        zone_mode = self._zone_mode
        if zone_mode is None:
            return HVACMode.OFF
        return ATW_ZONE_MODE_TO_HVAC_MODE.get(zone_mode, HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.control_atw_unit(self._unit_id, power=False)
        else:
            zone_mode = HVAC_MODE_TO_ATW_ZONE_MODE[hvac_mode]
            if self.zone_number == 1:
                await self.coordinator.client.control_atw_unit(
                    self._unit_id,
                    power=True,
                    operation_mode_zone1=zone_mode,
                )
            else:
                await self.coordinator.client.control_atw_unit(
                    self._unit_id,
                    power=True,
                    operation_mode_zone2=zone_mode,
                )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        if self.zone_number == 1:
            await self.coordinator.client.control_atw_unit(
                self._unit_id, set_temperature_zone1=temperature
            )
        else:
            await self.coordinator.client.control_atw_unit(
                self._unit_id, set_temperature_zone2=temperature
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the zone on."""
        await self.coordinator.client.control_atw_unit(self._unit_id, power=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self.coordinator.client.control_atw_unit(self._unit_id, power=False)
        await self.coordinator.async_request_refresh()
