"""Climate platform for MELCloud Home."""

from typing import Any

from aiomelcloudhome import (
    ATAFanSpeed,
    ATAOperationMode,
    ATAUnit,
    ATAVaneHorizontal,
    ATAVaneVertical,
    ATWUnit,
    ATWZoneMode,
)

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
    ATAFanSpeed.ONE: "speed_1",
    ATAFanSpeed.TWO: "speed_2",
    ATAFanSpeed.THREE: "speed_3",
    ATAFanSpeed.FOUR: "speed_4",
    ATAFanSpeed.FIVE: "speed_5",
}

HA_FAN_SPEED_TO_ATA: dict[str, ATAFanSpeed] = {
    value: key for key, value in ATA_FAN_SPEED_TO_HA.items()
}

ATA_VANE_VERTICAL_TO_HA: dict[ATAVaneVertical, str] = {
    ATAVaneVertical.AUTO: "auto",
    ATAVaneVertical.SWING: "swing",
    ATAVaneVertical.ONE: "position_1",
    ATAVaneVertical.TWO: "position_2",
    ATAVaneVertical.THREE: "position_3",
    ATAVaneVertical.FOUR: "position_4",
    ATAVaneVertical.FIVE: "position_5",
}

HA_VANE_VERTICAL_TO_ATA: dict[str, ATAVaneVertical] = {
    value: key for key, value in ATA_VANE_VERTICAL_TO_HA.items()
}

ATA_VANE_HORIZONTAL_TO_HA: dict[ATAVaneHorizontal, str] = {
    ATAVaneHorizontal.AUTO: "auto",
    ATAVaneHorizontal.SWING: "swing",
    ATAVaneHorizontal.LEFT: "left",
    ATAVaneHorizontal.LEFT_CENTRE: "left_centre",
    ATAVaneHorizontal.CENTRE: "centre",
    ATAVaneHorizontal.RIGHT_CENTRE: "right_centre",
    ATAVaneHorizontal.RIGHT: "right",
}

HA_VANE_HORIZONTAL_TO_ATA: dict[str, ATAVaneHorizontal] = {
    value: key for key, value in ATA_VANE_HORIZONTAL_TO_HA.items()
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
    coordinator = entry.runtime_data

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(ATAClimateEntity(coordinator, unit) for unit in units)

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        # Erwin: create zone 1 for all units, and zone 2 only when the unit supports it.
        async_add_entities(
            ATWZoneClimateEntity(coordinator, unit, zone_number)
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

    _async_add_new_ata_units(list(coordinator.ata_units.values()))
    _async_add_new_atw_units(list(coordinator.atw_units.values()))


class ATAClimateEntity(MelCloudHomeATAUnitEntity, ClimateEntity):
    """Climate entity for a MELCloud Home Air-to-Air unit."""

    _attr_translation_key = "ata_unit"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: MelCloudHomeCoordinator, unit: ATAUnit) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, unit)
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if unit.settings is not None:
            if unit.settings.get("VaneVerticalDirection") is not None:
                features |= ClimateEntityFeature.SWING_MODE
            if unit.settings.get("VaneHorizontalDirection") is not None:
                features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        self._attr_supported_features = features

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC modes supported by this unit based on its capabilities."""
        if self.unit.capabilities is None:
            return [
                HVACMode.OFF,
                HVACMode.HEAT,
                HVACMode.COOL,
                HVACMode.AUTO,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
            ]

        modes = [HVACMode.OFF, HVACMode.HEAT]
        if self.unit.capabilities.has_cool_operation_mode is not False:
            modes.append(HVACMode.COOL)
        if self.unit.capabilities.has_auto_operation_mode is not False:
            modes.append(HVACMode.AUTO)
        if self.unit.capabilities.has_dry_operation_mode is not False:
            modes.append(HVACMode.DRY)
        if self.unit.capabilities.has_fan_operation_mode is not False:
            modes.append(HVACMode.FAN_ONLY)
        return modes

    @property
    def fan_modes(self) -> list[str]:
        """Return fan modes supported by this unit based on its capabilities."""
        capabilities = self.unit.capabilities
        number = (
            capabilities.number_of_fan_speeds
            if capabilities is not None
            and capabilities.number_of_fan_speeds is not None
            else len(ATA_FAN_SPEED_TO_HA) - 1
        )
        all_speeds = list(ATA_FAN_SPEED_TO_HA.values())
        return [all_speeds[0], *all_speeds[1 : number + 1]]

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature."""
        return self.unit.room_temperature if self.unit else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.unit.set_temperature if self.unit else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        return (
            ATA_OPERATION_TO_HVAC_MODE.get(self.unit.operation_mode, HVACMode.OFF)
            if self.unit.power and self.unit.operation_mode
            else HVACMode.OFF
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return (
            ATA_FAN_SPEED_TO_HA.get(self.unit.set_fan_speed)
            if self.unit.set_fan_speed is not None
            else None
        )

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
        await self.coordinator.client.control_ata_unit(
            self._unit_id, set_temperature=kwargs[ATTR_TEMPERATURE]
        )
        await self.coordinator.async_request_refresh()

    @property
    def swing_modes(self) -> list[str] | None:
        """Return vertical vane positions as swing modes."""
        return (
            list(ATA_VANE_VERTICAL_TO_HA.values())
            if self.unit.settings.get("VaneVerticalDirection") is not None
            else None
        )

    @property
    def swing_mode(self) -> str | None:
        """Return the current vertical vane direction."""
        return (
            ATA_VANE_VERTICAL_TO_HA.get(self.unit.settings["VaneVerticalDirection"])
            if self.unit.settings.get("VaneVerticalDirection") is not None
            else None
        )

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        """Return horizontal vane positions as swing modes."""
        return (
            list(ATA_VANE_HORIZONTAL_TO_HA.values())
            if self.unit.settings.get("VaneHorizontalDirection") is not None
            else None
        )

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the current horizontal vane direction."""
        return (
            ATA_VANE_HORIZONTAL_TO_HA.get(self.unit.settings["VaneHorizontalDirection"])
            if self.unit.settings.get("VaneHorizontalDirection") is not None
            else None
        )

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal vane direction."""
        await self.coordinator.client.control_ata_unit(
            self._unit_id,
            vane_horizontal_direction=HA_VANE_HORIZONTAL_TO_ATA[swing_horizontal_mode],
        )
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical vane direction."""
        await self.coordinator.client.control_ata_unit(
            self._unit_id, vane_vertical_direction=HA_VANE_VERTICAL_TO_ATA[swing_mode]
        )
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self.coordinator.client.control_ata_unit(
            self._unit_id, set_fan_speed=HA_FAN_SPEED_TO_ATA[fan_mode]
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

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC modes supported by this zone based on unit capabilities."""
        modes = [HVACMode.OFF, HVACMode.HEAT]
        if (
            self.unit.capabilities is None
            or self.unit.capabilities.has_cooling_mode is not False
        ):
            modes.append(HVACMode.COOL)
        return modes

    @property
    def _zone_mode(self) -> ATWZoneMode | None:
        """Return the current ATW zone mode."""
        if self.zone_number == 1:
            return self.unit.operation_mode_zone1
        return self.unit.operation_mode_zone2

    @property
    def current_temperature(self) -> float | None:
        """Return the current zone temperature."""
        return (
            self.unit.room_temperature_zone1
            if self.zone_number == 1
            else self.unit.room_temperature_zone2
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the target zone temperature."""
        return (
            self.unit.set_temperature_zone1
            if self.zone_number == 1
            else self.unit.set_temperature_zone2
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        return (
            ATW_ZONE_MODE_TO_HVAC_MODE.get(self._zone_mode, HVACMode.OFF)
            if self.unit.power and self._zone_mode
            else HVACMode.OFF
        )

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
        temperature = kwargs[ATTR_TEMPERATURE]
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
