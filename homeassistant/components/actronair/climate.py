"""Climate platform for Actron Air Neo integration."""

from typing import Any

from actron_neo_api import ActronAirNeoStatus, ActronAirNeoZone

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActronNeoConfigEntry, ActronNeoSystemCoordinator

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
    entry: ActronNeoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air Neo climate entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    entities: list[ClimateEntity] = []

    for coordinator in system_coordinators.values():
        status = coordinator.data
        name = status.ac_system.system_name
        entities.append(ActronSystemClimate(coordinator, name))

        entities.extend(
            ActronZoneClimate(coordinator, zone)
            for zone in status.remote_zone_info
            if zone.exists
        )

    async_add_entities(entities)


class BaseClimateEntity(CoordinatorEntity[ActronNeoSystemCoordinator], ClimateEntity):
    """Base class for Actron Air Neo climate entities."""

    _attr_has_entity_name = True
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

    def __init__(
        self,
        coordinator: ActronNeoSystemCoordinator,
        name: str,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator)
        self._serial_number = coordinator.serial_number
        self._name = name


class ActronSystemClimate(BaseClimateEntity):
    """Representation of the Actron Air Neo system."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: ActronNeoSystemCoordinator,
        name: str,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator, name)
        serial_number = coordinator.serial_number
        self._attr_unique_id = serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=self._status.ac_system.system_name,
            manufacturer="Actron Air",
            model_id=self._status.ac_system.master_wc_model,
            sw_version=self._status.ac_system.master_wc_firmware_version,
            serial_number=serial_number,
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._status.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._status.max_temp

    @property
    def _status(self) -> ActronAirNeoStatus:
        """Get the current status from the coordinator."""
        return self.coordinator.data

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if not self._status.user_aircon_settings.is_on:
            return HVACMode.OFF

        mode = self._status.user_aircon_settings.mode
        return HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.get(mode, HVACMode.OFF)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self._status.user_aircon_settings.fan_mode
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
        api_fan_mode = FAN_MODE_MAPPING_HA_TO_ACTRONAIR.get(fan_mode.lower())
        await self._status.user_aircon_settings.set_fan_mode(api_fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        ac_mode = HVAC_MODE_MAPPING_HA_TO_ACTRONAIR.get(hvac_mode)
        await self._status.ac_system.set_system_mode(ac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs.get("temperature")
        await self._status.user_aircon_settings.set_temperature(temperature=temp)

    async def async_turn_on_continuous(self, continuous: bool) -> None:
        """Set the continuous mode."""
        await self._status.user_aircon_settings.set_continuous_mode(enabled=continuous)


class ActronZoneClimate(BaseClimateEntity):
    """Representation of a zone within the Actron Air system."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: ActronNeoSystemCoordinator,
        zone: ActronAirNeoZone,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator, zone.title)
        serial_number = coordinator.serial_number
        self._zone_id: int = zone.zone_id
        self._attr_unique_id: str = f"{self._serial_number}_zone_{zone.zone_id}"
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=zone.title,
            manufacturer="Actron Air",
            model="Zone",
            suggested_area=zone.title,
            via_device=(DOMAIN, serial_number),
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._zone.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._zone.max_temp

    @property
    def _zone(self) -> ActronAirNeoZone:
        """Get the current zone data from the coordinator."""
        status = self.coordinator.data
        return status.zones.get(self._zone_id)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self._zone.is_active:
            mode = self._zone.hvac_mode
            return HVAC_MODE_MAPPING_ACTRONAIR_TO_HA.get(mode, HVACMode.OFF)
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
        await self._zone.set_temperature(temperature=kwargs["temperature"])
