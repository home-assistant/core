"""Climate platform for Actron Air Neo integration."""

from typing import Any

from actron_neo_api import ActronNeoAPI

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ActronConfigEntry
from .const import DOMAIN
from .coordinator import ActronNeoDataUpdateCoordinator

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Actron Air Neo climate entities."""
    # Get the API and coordinator from the integration
    coordinator = entry.runtime_data

    # Add system-wide climate entity
    entities: list[ClimateEntity] = []

    for system in coordinator.api.systems:
        name = system["description"]
        serial_number = system["serial"]
        entities.append(ActronSystemClimate(coordinator, serial_number, name))

        zones = coordinator.data[serial_number].get("RemoteZoneInfo", [])

        zone_map = dict(enumerate(zones, start=0))
        for zone_number, zone in zone_map.items():
            if zone["NV_Exists"]:
                zone_name = zone["NV_Title"]
                entities.append(
                    ActronZoneClimate(
                        coordinator, serial_number, zone_name, zone_number
                    )
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

    def __init__(
        self,
        coordinator: ActronNeoDataUpdateCoordinator,
        serial_number: str,
        name: str,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator)
        self._api: ActronNeoAPI = coordinator.api
        self._serial_number: str = serial_number
        self._status = coordinator.data[serial_number]
        self._name: str = name
        self._attr_name: None = None
        self._attr_unique_id: str = serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=self._name,
            manufacturer="Actron Air",
            model=self._status.get("AirconSystem", {}).get("MasterWCModel"),
            sw_version=self._status.get("AirconSystem", {}).get(
                "MasterWCFirmwareVersion"
            ),
            serial_number=serial_number,
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        system_state = self._status.get("UserAirconSettings", {}).get("isOn")
        if not system_state:
            return HVACMode.OFF

        hvac_mode = self._status.get("UserAirconSettings", {}).get("Mode")
        return HVAC_MODE_MAPPING.get(hvac_mode, HVACMode.OFF)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC Modes."""
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        api_fan_mode = self._status["UserAirconSettings"]["FanMode"].upper()
        fan_mode_without_cont = api_fan_mode.split("+")[0]
        return FAN_MODE_MAPPING_REVERSE.get(fan_mode_without_cont, "AUTO")

    @property
    def current_humidity(self) -> float:
        """Return the current humidity."""
        return self._status.get("MasterInfo", {}).get("LiveHumidity_pc")

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._status.get("MasterInfo", {}).get("LiveTemp_oC")

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._status.get("UserAirconSettings", {}).get(
            "TemperatureSetpoint_Cool_oC"
        )

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        return (
            self._status.get("NV_Limits", {})
            .get("UserSetpoint_oC", {})
            .get("setCool_Min", 16.0)
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        return (
            self._status.get("NV_Limits", {})
            .get("UserSetpoint_oC", {})
            .get("setCool_Max", 32.0)
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set a new fan mode."""
        api_fan_mode = FAN_MODE_MAPPING.get(fan_mode.lower())
        await self._api.set_fan_mode(self._serial_number, fan_mode=api_fan_mode)
        self._status["UserAirconSettings"]["FanMode"] = api_fan_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        ac_mode = HVAC_MODE_MAPPING_REVERSE.get(hvac_mode)
        if not ac_mode:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        if hvac_mode == HVACMode.OFF:
            await self._api.set_system_mode(self._serial_number, is_on=False)
        else:
            await self._api.set_system_mode(
                self._serial_number, is_on=True, mode=ac_mode
            )
        self._status["UserAirconSettings"]["Mode"] = hvac_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs.get("temperature")
        hvac_mode = self.hvac_mode.lower()

        if hvac_mode == HVACMode.COOL:
            await self._api.set_temperature(
                self._serial_number,
                mode="COOL",
                temperature=temp,
            )
        elif hvac_mode == HVACMode.HEAT:
            await self._api.set_temperature(
                self._serial_number,
                mode="HEAT",
                temperature=temp,
            )
        elif hvac_mode == HVACMode.AUTO:
            await self._api.set_temperature(
                self._serial_number,
                mode="AUTO",
                temperature={"cool": temp, "heat": temp},
            )
        else:
            raise ValueError(f"Mode {hvac_mode} is invalid.")
        self._status["MasterInfo"]["LiveTemp_oC"] = temp

    async def async_turn_on_continuous(self, continuous: bool) -> None:
        """Set the continuous mode."""
        await self._api.set_fan_mode(
            self._serial_number, fan_mode=self._attr_fan_mode, continuous=continuous
        )


class ActronZoneClimate(CoordinatorEntity, ClimateEntity):
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
        zone_name: str,
        zone_number: int,
    ) -> None:
        """Initialize an Actron Air Neo unit."""
        super().__init__(coordinator)
        self._api: ActronNeoAPI = coordinator.api
        self._serial_number: str = serial_number
        self._ac_status = coordinator.data[serial_number]
        self._name: str = zone_name
        self._zone_number = zone_number
        self._attr_name: None = None
        self._attr_unique_id = f"{self._serial_number}_zone_{self._zone_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._name,
            manufacturer="Actron Air",
            model="Zone",
            suggested_area=self._name,
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if not self._ac_status["UserAirconSettings"]["isOn"]:
            return HVACMode.OFF

        if self._ac_status["UserAirconSettings"]["EnabledZones"][self._zone_number]:
            hvac_mode = self._ac_status["UserAirconSettings"]["Mode"]
            return HVAC_MODE_MAPPING.get(hvac_mode, HVACMode.OFF)

        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return HVAC Modes."""
        return [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        zone = self._ac_status["RemoteZoneInfo"][self._zone_number]
        return zone["LiveHumidity_pc"]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        zone = self._ac_status["RemoteZoneInfo"][self._zone_number]
        return zone["LiveTemp_oC"]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        zone = self._ac_status["RemoteZoneInfo"][self._zone_number]
        return zone["TemperatureSetpoint_Cool_oC"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature that can be set."""
        min_setpoint = self._ac_status["NV_Limits"]["UserSetpoint_oC"]["setCool_Min"]
        target_setpoint = self._ac_status["UserAirconSettings"][
            "TemperatureSetpoint_Cool_oC"
        ]
        temp_variance = self._ac_status["UserAirconSettings"][
            "ZoneTemperatureSetpointVariance_oC"
        ]
        if min_setpoint > target_setpoint - temp_variance:
            return min_setpoint
        return target_setpoint - temp_variance

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature that can be set."""
        max_setpoint = self._ac_status["NV_Limits"]["UserSetpoint_oC"]["setCool_Max"]
        target_setpoint = self._ac_status["UserAirconSettings"][
            "TemperatureSetpoint_Cool_oC"
        ]
        temp_variance = self._ac_status["UserAirconSettings"][
            "ZoneTemperatureSetpointVariance_oC"
        ]
        if max_setpoint < target_setpoint + temp_variance:
            return max_setpoint
        return target_setpoint + temp_variance

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        is_enabled = hvac_mode != HVACMode.OFF

        await self._api.set_zone(
            serial_number=self._serial_number,
            zone_number=self._zone_number,
            is_enabled=is_enabled,
        )
        self._ac_status["UserAirconSettings"]["EnabledZones"][self._zone_number] = (
            is_enabled
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature."""
        temp = kwargs["temperature"]
        hvac_mode = self.hvac_mode

        if hvac_mode == HVACMode.COOL:
            mode = "COOL"
        elif hvac_mode == HVACMode.HEAT:
            mode = "HEAT"
        elif hvac_mode == HVACMode.AUTO:
            mode = "AUTO"
            temp = {"cool": temp, "heat": temp}

        await self._api.set_temperature(
            serial_number=self._serial_number,
            mode=mode,
            temperature=temp,
            zone=self._zone_number,
        )
        self._ac_status["RemoteZoneInfo"][self._zone_number]["LiveTemp_oC"] = temp
