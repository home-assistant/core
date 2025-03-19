"""Climate Entity for the master control as well as Zones."""

from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    AC_SYSTEMS_COORDINATOR,
    DOMAIN,
    SELECTED_AC_SERIAL,
    SYSTEM_STATUS_COORDINATOR,
)
from .coordinator import (
    ActronAirACSystemsDataCoordinator,
    ActronAirSystemStatusDataCoordinator,
)
from .entity import ActronAirWallController, ActronAirZoneDevice
from .utility import (
    get_ActronAir_ac_mode_from_HASS_ac_mode,
    get_ActronAir_fan_mode_from_HASS_fan_mode,
    get_HASS_ac_mode_from_ActronAir_ac_mode,
    get_HASS_fan_mode_from_ActronAir_fan_mode,
)

SUPPORTED_HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.FAN_ONLY,
    HVACMode.OFF,
]
SUPPORTED_FAN_MODES = [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Actron Air climate entity."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    ac_systems_coordinator = coordinators[AC_SYSTEMS_COORDINATOR]
    status_coordinator: ActronAirSystemStatusDataCoordinator = coordinators[
        SYSTEM_STATUS_COORDINATOR
    ]

    await ac_systems_coordinator.async_config_entry_first_refresh()
    await status_coordinator.async_config_entry_first_refresh()

    selected_ac_serial = hass.data[DOMAIN].get(SELECTED_AC_SERIAL, None)

    if selected_ac_serial:
        entities: list[ClimateEntity] = [
            ActronAirClimate(
                ac_systems_coordinator, status_coordinator, selected_ac_serial
            )
        ]  # wall Controller

        zoneId: int = 1
        if status_coordinator.acSystemStatus is not None:
            for zoneInfo in status_coordinator.acSystemStatus.RemoteZoneInfo:
                if zoneInfo.CanOperate:
                    entities.append(
                        ActronAirZoneClimate(
                            status_coordinator, selected_ac_serial, zoneId
                        )
                    )  # Zone entity
                    zoneId += 1
                else:
                    break

        async_add_entities(entities, update_before_add=True)


class ActronAirClimate(ActronAirWallController, ClimateEntity):
    """Representation of an Actron Air AC system."""

    def __init__(
        self,
        ac_systems_coordinator: ActronAirACSystemsDataCoordinator,
        status_coordinator: ActronAirSystemStatusDataCoordinator,
        selected_ac_serial: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(status_coordinator, selected_ac_serial)
        self.ac_systems_coordinator = ac_systems_coordinator
        self.status_coordinator = status_coordinator

        # Fetch AC system details
        self.ac_data = status_coordinator.acSystemStatus
        self._attr_name = (
            f"AC {self.ac_data.SystemName + ' (' + self.ac_data.MasterSerial + ')'}"
        )
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{DOMAIN}_{self.ac_data.MasterSerial}_climate"
        self._attr_hvac_modes = SUPPORTED_HVAC_MODES
        self._attr_fan_modes = SUPPORTED_FAN_MODES
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.ac_data.IsOn is False:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = get_HASS_ac_mode_from_ActronAir_ac_mode(
                self.status_coordinator.acSystemStatus.Mode
            )
        self._attr_target_temperature = self.ac_data.TemprSetPoint_Cool
        self._attr_current_temperature = self.ac_data.LiveTemp_oC
        self._attr_current_humidity = self.ac_data.LiveHumidity_pc
        self._is_on = self.ac_data.IsOn

    @property
    def name(self) -> str | None:
        """Return the name."""
        self._attr_name = f"AC {self.status_coordinator.acSystemStatus.SystemName + ' (' + self.status_coordinator.acSystemStatus.MasterSerial + ')'}"
        return self._attr_name

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if self.status_coordinator.acSystemStatus.IsOn is False:
            self._attr_hvac_mode = HVACMode.OFF
            self._is_on = False
        else:
            self._attr_hvac_mode = get_HASS_ac_mode_from_ActronAir_ac_mode(
                self.status_coordinator.acSystemStatus.Mode
            )
            self._is_on = True
        return self._attr_hvac_mode

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        self._attr_target_temperature = (
            self.status_coordinator.acSystemStatus.TemprSetPoint_Cool
        )
        return self._attr_target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        self._attr_current_temperature = (
            self.status_coordinator.acSystemStatus.LiveTemp_oC
        )
        return self._attr_current_temperature

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        self._attr_current_humidity = self.ac_data.LiveHumidity_pc
        return self._attr_current_humidity

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        self._attr_fan_mode = get_HASS_fan_mode_from_ActronAir_fan_mode(
            self.status_coordinator.acSystemStatus.FanMode
        )
        return self._attr_fan_mode

    def getCommandJSONString(self, literal: str, value: str) -> Any:
        """Get JSON payload for set-settings Command."""
        return {
            "command": {
                "type": "set-settings",
                f"{literal}": value,
            }
        }

    def getCommandJSONStringFromList(
        self, literals: list[str], values: list[Any]
    ) -> Any:
        """Generate a JSON string command from lists of literals and values."""
        if len(literals) != len(values):
            raise ValueError("Lists 'literals' and 'values' must have the same length")

        settings = {literals[i]: values[i] for i in range(len(literals))}
        command = {"command": {"type": "set-settings"}}
        command["command"].update(settings)
        return command

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode not in SUPPORTED_HVAC_MODES:
            raise ValueError(f"Unsupported mode: {hvac_mode}")

        if hvac_mode == HVACMode.OFF:
            command = self.getCommandJSONString("UserAirconSettings.isOn", "false")
            powerState = False
        else:
            actron_hvac_mode = get_ActronAir_ac_mode_from_HASS_ac_mode(hvac_mode)
            literals = ["UserAirconSettings.Mode", "UserAirconSettings.isOn"]
            values = [actron_hvac_mode, "true"]
            command = self.getCommandJSONStringFromList(literals, values)
            powerState = True

        await self.status_coordinator.aa_api.async_sendCommand(
            self.serial_number, command
        )
        self._is_on = powerState
        self._attr_hvac_mode = hvac_mode
        await self.status_coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        keys = [
            "UserAirconSettings.TemperatureSetpoint_Cool_oC",
            "UserAirconSettings.TemperatureSetpoint_Heat_oC",
        ]
        values = [temperature, temperature]
        command = self.getCommandJSONStringFromList(keys, values)
        await self.status_coordinator.aa_api.async_sendCommand(
            self.serial_number, command
        )
        self._attr_target_temperature = temperature
        await self.status_coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        if fan_mode not in SUPPORTED_FAN_MODES:
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        actron_fan_mode = get_ActronAir_fan_mode_from_HASS_fan_mode(fan_mode)
        command = self.getCommandJSONString(
            "UserAirconSettings.FanMode", actron_fan_mode
        )
        await self.status_coordinator.aa_api.async_sendCommand(
            self.serial_number, command
        )

        self._attr_fan_mode = fan_mode
        await self.status_coordinator.async_request_refresh()


class ActronAirZoneClimate(ActronAirZoneDevice, ClimateEntity):
    """Climate entity for individual zones."""

    def __init__(
        self,
        status_coordinator: ActronAirSystemStatusDataCoordinator,
        serial_number: str,
        zone_id: int,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(status_coordinator, serial_number, zone_id)
        self.status_coordinator = status_coordinator
        self.ac_data = status_coordinator.acSystemStatus
        zoneInfo = self.ac_data.RemoteZoneInfo[zone_id - 1]

        self.zone_id = zone_id
        self._attr_name = zoneInfo.NV_Title
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )

        if zoneInfo.NV_ITC:
            self._attr_supported_features = (
                ClimateEntityFeature.TURN_OFF
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TARGET_TEMPERATURE
            )
            self._attr_target_temperature = zoneInfo.TemprSetPoint_Cool

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{DOMAIN}_zone_{zone_id}_climate"
        self.serial_number = serial_number
        self._is_on = self.status_coordinator.acSystemStatus.EnabledZones[
            self.zone_id - 1
        ]
        if (
            self.ac_data.RemoteZoneInfo[self.zone_id - 1].NV_ITD
            and zoneInfo.LiveTemp_oC < 100.0
        ):
            self._attr_current_temperature = zoneInfo.LiveTemp_oC

        if self.ac_data.RemoteZoneInfo[self.zone_id - 1].NV_IHD:
            self._attr_current_humidity = zoneInfo.LiveHumidity_pc

    @property
    def name(self) -> str:
        """Return device name."""
        zoneInfo = self.status_coordinator.acSystemStatus.RemoteZoneInfo[
            self.zone_id - 1
        ]
        self._attr_name = zoneInfo.NV_Title
        return self._attr_name

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return whether the zone is ON or OFF."""
        self._is_on = self.status_coordinator.acSystemStatus.EnabledZones[
            self.zone_id - 1
        ]
        return HVACMode.HEAT_COOL if self._is_on else HVACMode.OFF

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        self._attr_target_temperature = (
            self.status_coordinator.acSystemStatus.RemoteZoneInfo[
                self.zone_id - 1
            ].TemprSetPoint_Cool
        )
        return self._attr_target_temperature

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        zoneInfo = self.status_coordinator.acSystemStatus.RemoteZoneInfo[
            self.zone_id - 1
        ]
        if zoneInfo.LiveTemp_oC < 100.0 and zoneInfo.NV_ITD:
            self._attr_current_temperature = (
                self.status_coordinator.acSystemStatus.RemoteZoneInfo[
                    self.zone_id - 1
                ].LiveTemp_oC
            )
            return self._attr_current_temperature
        return None

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        zoneInfo = self.status_coordinator.acSystemStatus.RemoteZoneInfo[
            self.zone_id - 1
        ]
        if zoneInfo.LiveHumidity_pc is not None and zoneInfo.NV_IHD:
            self._attr_current_humidity = zoneInfo.LiveHumidity_pc
            return self._attr_current_humidity
        return None

    @property
    def available(self) -> bool:
        """Return True if the AC system has been Online."""
        self._attr_available = self.status_coordinator.acSystemStatus.IsOnline
        return self._attr_available

    def getZoneOnOffCommand(self, isON: bool, zoneId: int) -> Any:
        """Generate a command to turn a specific zone on or off."""
        enabled_zones = self.status_coordinator.acSystemStatus.EnabledZones

        if not (0 <= zoneId < len(enabled_zones)):
            raise ValueError(
                f"Invalid zoneId {zoneId}. Must be between 0 and {len(enabled_zones) - 1}."
            )
        updated_zones = enabled_zones[:]
        updated_zones[zoneId] = isON
        return {
            "command": {
                "type": "set-settings",
                "UserAirconSettings.EnabledZones": updated_zones,
            }
        }

    def getCommandJSONStringFromList(
        self, literals: list[str], values: list[Any]
    ) -> Any:
        """Generate a JSON string command from lists of literals and values."""
        if len(literals) != len(values):
            raise ValueError("Lists 'literals' and 'values' must have the same length")

        settings = {literals[i]: values[i] for i in range(len(literals))}
        command = {"command": {"type": "set-settings"}}
        command["command"].update(settings)
        return command

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the AC system ON or OFF."""
        if hvac_mode == HVACMode.HEAT_COOL:
            command = self.getZoneOnOffCommand(True, self.zone_id - 1)
            await self.status_coordinator.aa_api.async_sendCommand(
                self.serial_number, command
            )
            self._is_on = True
        elif hvac_mode == HVACMode.OFF:
            command = self.getZoneOnOffCommand(False, self.zone_id - 1)
            await self.status_coordinator.aa_api.async_sendCommand(
                self.serial_number, command
            )
            self._is_on = False

        await self.coordinator.async_request_refresh()  # Refresh state

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        keys = [
            "RemoteZoneInfo[" + str(self.zone_id - 1) + "].TemperatureSetpoint_Cool_oC",
            "RemoteZoneInfo["
            + str(self.zone_id - 1)
            + "].TemperatureSetpoint_Heat_oC,",
        ]
        values = [temperature, temperature]
        command = self.getCommandJSONStringFromList(keys, values)
        await self.status_coordinator.aa_api.async_sendCommand(
            self.serial_number, command
        )
        self._attr_target_temperature = temperature
        await self.status_coordinator.async_request_refresh()
