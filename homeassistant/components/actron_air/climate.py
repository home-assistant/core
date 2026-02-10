"""Climate platform for Actron Air integration."""

from typing import Any

from actron_neo_api import ActronAirStatus, ActronAirZone

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirAcEntity, ActronAirZoneEntity

PARALLEL_UPDATES = 0

FAN_MODE_MAPPING_ACTRONAIR_TO_HA = {
    "AUTO": FAN_AUTO,
    "LOW": FAN_LOW,
    "MED": FAN_MEDIUM,
    "HIGH": FAN_HIGH,
}
FAN_MODE_MAPPING_HA_TO_ACTRONAIR = {
    v: k for k, v in FAN_MODE_MAPPING_ACTRONAIR_TO_HA.items()
}
HVAC_MODE_MAPPING_ACTRONAIR_TO_HA = {
    "COOL": HVACMode.COOL,
    "HEAT": HVACMode.HEAT,
    "FAN": HVACMode.FAN_ONLY,
    "AUTO": HVACMode.AUTO,
    "OFF": HVACMode.OFF,
}
HVAC_MODE_MAPPING_HA_TO_ACTRONAIR = {
    v: k for k, v in HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air climate entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[ClimateEntity] = []

    for coordinator in system_coordinators.values():
        status = coordinator.data
        entities.append(ActronSystemClimate(coordinator))

        entities.extend(
            ActronZoneClimate(coordinator, zone)
            for zone in status.remote_zone_info
            if zone.exists
        )

    async_add_entities(entities)


class ActronAirClimateEntity(ClimateEntity):
    """Base class for Actron Air climate entities."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_name = None
    _attr_fan_modes = list(FAN_MODE_MAPPING_ACTRONAIR_TO_HA.values())
    _attr_hvac_modes = list(HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.values())


class ActronSystemClimate(ActronAirAcEntity, ActronAirClimateEntity):
    """Representation of the Actron Air system."""

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
    ) -> None:
        """Initialize an Actron Air unit."""
        super().__init__(coordinator)
        self._attr_unique_id = self._serial_number

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._status.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._status.max_temp

    @property
    def _status(self) -> ActronAirStatus:
        """Get the current status from the coordinator."""
        return self.coordinator.data

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if not self._status.user_aircon_settings.is_on:
            return HVACMode.OFF

        mode = self._status.user_aircon_settings.mode
        return HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.get(mode)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self._status.user_aircon_settings.base_fan_mode
        return FAN_MODE_MAPPING_ACTRONAIR_TO_HA.get(fan_mode)

    @property
    def current_humidity(self) -> float:
        """Return the current humidity."""
        return self._status.master_info.live_humidity_pc

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._status.master_info.live_temp_c

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._status.user_aircon_settings.temperature_setpoint_cool_c

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        api_fan_mode = FAN_MODE_MAPPING_HA_TO_ACTRONAIR.get(fan_mode)
        await self._status.user_aircon_settings.set_fan_mode(api_fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        ac_mode = HVAC_MODE_MAPPING_HA_TO_ACTRONAIR.get(hvac_mode)
        await self._status.ac_system.set_system_mode(ac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self._status.user_aircon_settings.set_temperature(temperature=temp)


class ActronZoneClimate(ActronAirZoneEntity, ActronAirClimateEntity):
    """Representation of a zone within the Actron Air system."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        zone: ActronAirZone,
    ) -> None:
        """Initialize an Actron Air unit."""
        super().__init__(coordinator, zone)
        self._attr_unique_id: str = self._zone_identifier

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._zone.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._zone.max_temp

    @property
    def _zone(self) -> ActronAirZone:
        """Get the current zone data from the coordinator."""
        status = self.coordinator.data
        return status.zones[self._zone_id]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if self._zone.is_active:
            mode = self._zone.hvac_mode
            return HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.get(mode)
        return HVACMode.OFF

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._zone.humidity

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone.live_temp_c

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._zone.temperature_setpoint_cool_c

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        is_enabled = hvac_mode != HVACMode.OFF
        await self._zone.enable(is_enabled)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        await self._zone.set_temperature(temperature=kwargs.get(ATTR_TEMPERATURE))
