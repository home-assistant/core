"""Climate platform for Actron Air Neo integration."""

from typing import Any

from actron_neo_api import ActronAirNeoStatus, ActronAirNeoZone

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ActronConfigEntry
from .const import DOMAIN
from .coordinator import ActronNeoDataUpdateCoordinator

PARALLEL_UPDATES = 0

FAN_MODE_MAPPING = {
    "auto": "AUTO",
    "low": "LOW",
    "medium": "MED",
    "high": "HIGH",
}
FAN_MODE_MAPPING_REVERSE = {v: k for k, v in FAN_MODE_MAPPING.items()}
HVAC_MODE_MAPPING = {
    "COOL": HVACMode.COOL,
    "HEAT": HVACMode.HEAT,
    "FAN": HVACMode.FAN_ONLY,
    "AUTO": HVACMode.AUTO,
    "OFF": HVACMode.OFF,
}
HVAC_MODE_MAPPING_REVERSE = {v: k for k, v in HVAC_MODE_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air Neo climate entities."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = []

    for system in coordinator.systems:
        name = system["description"]
        serial_number = system["serial"]
        entities.append(ActronSystemClimate(coordinator, serial_number, name))
        status = coordinator.api.state_manager.get_status(serial_number)

        entities.extend(
            ActronZoneClimate(coordinator, serial_number, zone)
            for zone in status.remote_zone_info
            if zone.exists
        )

    async_add_entities(entities)


class ActronSystemClimate(
    CoordinatorEntity[ActronNeoDataUpdateCoordinator], ClimateEntity
):
    """Representation of the Actron Air Neo system."""

    _attr_has_entity_name = True
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_name: None = None
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]

    def __init__(
        self,
        coordinator: ActronNeoDataUpdateCoordinator,
        serial_number: str,
        name: str,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator)
        self._serial_number: str = serial_number
        self._name: str = name
        self._attr_unique_id: str = serial_number
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=self._status.ac_system.system_name,
            manufacturer="Actron Air",
            model=self._status.ac_system.master_wc_model,
            sw_version=self._status.ac_system.master_wc_firmware_version,
            serial_number=serial_number,
        )

    @property
    def _status(self) -> ActronAirNeoStatus:
        """Get the current status from the coordinator."""
        return self.coordinator.get_status(self._serial_number)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if not self._status.user_aircon_settings.is_on:
            return HVACMode.OFF

        mode = self._status.user_aircon_settings.mode
        return HVAC_MODE_MAPPING.get(mode, HVACMode.OFF)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self._status.user_aircon_settings.fan_mode
        return FAN_MODE_MAPPING_REVERSE.get(fan_mode)

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

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._status.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._status.max_temp

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        api_fan_mode = FAN_MODE_MAPPING.get(fan_mode.lower())
        await self._status.user_aircon_settings.set_fan_mode(api_fan_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        ac_mode = HVAC_MODE_MAPPING_REVERSE.get(hvac_mode)
        await self._status.ac_system.set_system_mode(ac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs.get("temperature")
        await self._status.user_aircon_settings.set_temperature(temperature=temp)

    async def async_turn_on_continuous(self, continuous: bool) -> None:
        """Set the continuous mode."""
        await self._status.user_aircon_settings.set_continuous_mode(enabled=continuous)


class ActronZoneClimate(
    CoordinatorEntity[ActronNeoDataUpdateCoordinator], ClimateEntity
):
    """Representation of a zone within the Actron Air system."""

    _attr_has_entity_name = True
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: ActronNeoDataUpdateCoordinator,
        serial_number: str,
        zone: ActronAirNeoZone,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator)
        self._serial_number = serial_number
        self._zone_id: int = zone.zone_id
        self._attr_name: None = None
        self._attr_unique_id: str = f"{serial_number}_zone_{zone.zone_id}"
        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=zone.title,
            manufacturer="Actron Air",
            model="Zone",
            suggested_area=zone.title,
            via_device=(DOMAIN, serial_number),
        )

    @property
    def _zone(self) -> ActronAirNeoZone:
        """Get the current zone data from the coordinator."""
        status = self.coordinator.get_status(self._serial_number)
        return status.zones.get(self._zone_id)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self._zone.is_active:
            mode = self._zone.hvac_mode
            return HVAC_MODE_MAPPING.get(mode, HVACMode.OFF)
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC Modes."""
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]

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

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return self._zone.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return self._zone.max_temp

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        is_enabled = hvac_mode != HVACMode.OFF
        await self._zone.enable(is_enabled)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        await self._zone.set_temperature(temperature=kwargs["temperature"])
