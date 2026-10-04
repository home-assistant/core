"""Support for the Daikin HVAC."""

from datetime import timedelta
import logging
import re
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_HOMEKIT_FAN_MODE_ALIASES, DOMAIN, FANMODE_FIXED
from .coordinator import OnectaDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

PRESET_MODES = (PRESET_BOOST, PRESET_AWAY, PRESET_COMFORT, PRESET_ECO)

DAIKIN_FAN_MODE_QUIET = "quiet"

HOMEKIT_FIXED_FAN_MODE_ALIASES = {
    FAN_MIDDLE: "2",
    FAN_MEDIUM: "3",
    FAN_HIGH: "5",
}

DAIKIN_HVAC_TO_HA = {
    "fanOnly": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "cooling": HVACMode.COOL,
    "heating": HVACMode.HEAT,
    "heatingDay": HVACMode.HEAT,
    "heatingNight": HVACMode.HEAT,
    "auto": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
    "humidification": HVACMode.DRY,
}

HA_PRESET_TO_DAIKIN = {
    PRESET_AWAY: "holidayMode",
    PRESET_NONE: "off",
    PRESET_BOOST: "powerfulMode",
    PRESET_COMFORT: "comfortMode",
    PRESET_ECO: "econoMode",
}

SENSORY_DATA_MODEL_ATTRIBUTES = {
    "roomTemperature": "room_temperature",
    "outdoorTemperature": "outdoor_temperature",
    "leavingWaterTemperature": "leaving_water_temperature",
    "tankTemperature": "tank_temperature",
    "roomHumidity": "room_humidity",
    "pm1Concentration": "pm1_concentration",
    "pm25Concentration": "pm25_concentration",
    "pm10Concentration": "pm10_concentration",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    for device in (coordinator.data or {}).values():
        async_add_entities(
            _create_climate_entities(device, coordinator), update_before_add=False
        )


def _create_climate_entities(
    device: Any, coordinator: OnectaDataUpdateCoordinator
) -> list[DaikinClimate]:
    """Create climate entities for all independently controllable zones."""
    entities: list[DaikinClimate] = []
    device_model = device.device.device_model
    for management_point in device.device.management_points_by_type("climateControl"):
        modes: list[str] = []
        if management_point.temperature_control is not None:
            for (
                operation_mode
            ) in management_point.temperature_control.value.operation_modes.values():
                modes.extend(operation_mode.setpoints)
        # The setpoints may recur across operation modes, but each management
        # point represents an independently controllable climate zone.
        modes = list(dict.fromkeys(modes))
        _LOGGER.info(
            "Climate: Device '%s', management point '%s' has modes %s",
            device_model,
            management_point.embedded_id,
            modes,
        )
        entities.extend(
            DaikinClimate(device, mode, coordinator, management_point.embedded_id)
            for mode in modes
        )
    return entities


class DaikinClimate(CoordinatorEntity[OnectaDataUpdateCoordinator], ClimateEntity):
    """Representation of a Daikin HVAC."""

    # Setpoint is the setpoint string under
    # temperatureControl/value/operationsModes/mode/setpoints, for example roomTemperature/leavingWaterOffset
    def __init__(
        self, device, setpoint, coordinator: OnectaDataUpdateCoordinator, embedded_id
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        _LOGGER.info(
            "Device '%s' initializing Daikin Climate for controlling %s",
            device.name,
            setpoint,
        )
        self._device = device
        self._embedded_id = embedded_id
        self._setpoint = setpoint
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._setpoint}"
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id)},
            "name": self._device.name,
        }
        self._attr_has_entity_name = True
        if setpoint == "roomTemperature":
            self._attr_translation_key = "roomtemperature"
        self._device.fill_gateway_device_info(self._attr_device_info)
        self.update_state()

    def update_state(self) -> None:
        """Refresh all state attributes from the device."""
        # Successful writes update the typed model optimistically so Home
        # Assistant reflects the new state without waiting for the next poll.
        self._attr_supported_features = self.get_supported_features()
        self._attr_current_temperature = self.get_current_temperature()
        self._attr_max_temp = self.get_max_temp()
        self._attr_min_temp = self.get_min_temp()
        self._attr_target_temperature_step = self.get_target_temperature_step()
        self._attr_target_temperature = self.get_target_temperature()
        self._attr_hvac_modes = self.get_hvac_modes()
        self._attr_swing_modes = self.get_swing_modes()
        self._attr_swing_horizontal_modes = self.get_swing_horizontal_modes()
        self._attr_preset_modes = self.get_preset_modes()
        self._attr_fan_modes = self.get_fan_modes()
        self._attr_hvac_mode = self.get_hvac_mode()
        self._attr_swing_mode = self.get_swing_mode()
        self._attr_swing_horizontal_mode = self.get_swing_horizontal_mode()
        self._attr_preset_mode = self.get_preset_mode()
        self._attr_fan_mode = self.get_fan_mode()

    def _raise_command_failed(self, command: str) -> None:
        """Raise an error when Daikin rejects a command."""
        raise HomeAssistantError(f"Failed to {command} for {self._device.name}")

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return (
            super().available
            and self._device.available
            and self.climate_control() is not None
        )

    def climate_control(self):
        """Return the typed climate-control management point."""
        return self._device.management_point(self._embedded_id)

    def operation_mode(self):
        """Return the operation-mode characteristic."""
        cc = self.climate_control()
        return cc.operation_mode if cc is not None else None

    def fan_operation(self, operation_mode: str | None = None):
        """Return fan controls for an operation mode."""
        cc = self.climate_control()
        if cc is None or cc.fan_control is None:
            return None
        if operation_mode is None:
            if cc.operation_mode is None:
                return None
            operation_mode = cc.operation_mode.value
        return cc.fan_control.value.operation_modes.get(operation_mode)

    def preset_characteristic(self, daikin_mode):
        """Return a preset characteristic by Daikin API name."""
        cc = self.climate_control()
        if cc is None:
            return None
        if daikin_mode == "holidayMode":
            return cc.holiday_mode
        return cc.characteristic(daikin_mode)

    @property
    def _homekit_fan_mode_aliases_enabled(self):
        """Return whether HomeKit fan mode aliases are enabled."""
        return self.coordinator.options.get(CONF_HOMEKIT_FAN_MODE_ALIASES, False)

    def homekit_fan_mode_aliases(self, fan_speed):
        """Return HomeKit fan mode aliases available for the fan speed data."""
        aliases: dict[str, str] = {}
        if not self._homekit_fan_mode_aliases_enabled:
            return aliases

        current_mode_values = fan_speed.current_mode.values or []
        if DAIKIN_FAN_MODE_QUIET in current_mode_values:
            aliases[FAN_LOW] = DAIKIN_FAN_MODE_QUIET

        if FANMODE_FIXED not in current_mode_values or not fan_speed.modes:
            return aliases
        fixed_mode = fan_speed.modes.get(FANMODE_FIXED)
        if (
            fixed_mode is None
            or fixed_mode.min_value is None
            or fixed_mode.max_value is None
            or fixed_mode.step_value is None
        ):
            return aliases
        fixed_values = {
            str(value)
            for value in range(
                int(fixed_mode.min_value),
                int(fixed_mode.max_value) + 1,
                int(fixed_mode.step_value),
            )
        }
        aliases.update(
            {
                alias: daikin_mode
                for alias, daikin_mode in HOMEKIT_FIXED_FAN_MODE_ALIASES.items()
                if daikin_mode in fixed_values
            }
        )
        return aliases

    def get_homekit_fan_mode(self, fan_speed, fan_mode):
        """Return the HomeKit alias for a Daikin fan mode when available."""
        if not self._homekit_fan_mode_aliases_enabled:
            return fan_mode

        aliases = self.homekit_fan_mode_aliases(fan_speed)
        for alias, daikin_mode in aliases.items():
            if fan_mode == daikin_mode:
                return alias

        return fan_mode

    def resolve_homekit_fan_mode_alias(self, fan_speed, fan_mode):
        """Return the Daikin fan mode represented by a HomeKit alias."""
        return self.homekit_fan_mode_aliases(fan_speed).get(fan_mode, fan_mode)

    def setpoint(self, operation_mode: str | None = None):
        """Return a setpoint for an operation mode."""
        cc = self.climate_control()
        if cc is None or cc.temperature_control is None:
            return None
        if operation_mode is None:
            if cc.operation_mode is None:
                return None
            operation_mode = cc.operation_mode.value
        mode_setpoints = cc.temperature_control.value.operation_modes.get(
            operation_mode
        )
        if mode_setpoints is None:
            return None
        return mode_setpoints.setpoints.get(self._setpoint)

    def sensory_data(self, setpoint):
        """Return a sensory characteristic by Daikin API name."""
        cc = self.climate_control()
        if cc is None or cc.sensory_data is None:
            return None
        attribute = SENSORY_DATA_MODEL_ATTRIBUTES.get(setpoint)
        return (
            getattr(cc.sensory_data.value, attribute) if attribute is not None else None
        )

    def get_supported_features(self):
        """Return the features supported by this climate entity."""
        supported_features = 0
        if hasattr(ClimateEntityFeature, "TURN_OFF"):
            supported_features = (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
        setpointdict = self.setpoint()
        if setpointdict is not None and setpointdict.settable:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if len(self.get_preset_modes()) > 1:
            supported_features |= ClimateEntityFeature.PRESET_MODE
        cc = self.climate_control()
        if cc is not None:
            fan_operation = self.fan_operation()
            if fan_operation is not None:
                if fan_operation.fan_speed is not None:
                    supported_features |= ClimateEntityFeature.FAN_MODE
                if fan_operation.fan_direction is not None:
                    if fan_operation.fan_direction.vertical is not None:
                        supported_features |= ClimateEntityFeature.SWING_MODE
                    if fan_operation.fan_direction.horizontal is not None:
                        supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

            _LOGGER.debug(
                "Device '%s' supports features %s",
                self._device.name,
                supported_features,
            )

        return supported_features

    @property
    @override
    def name(self) -> str | None:
        """Return the readable setpoint name."""
        myname = self._setpoint[0].upper() + self._setpoint[1:]
        readable = re.findall("[A-Z][^A-Z]*", myname)
        return f"{' '.join(readable)}"

    def get_current_temperature(self):
        """Return the current temperature for this setpoint."""
        current_temp = None
        sensory_data = self.sensory_data(self._setpoint)
        # Check if there is a sensoryData which is for the same setpoint, if so, return that
        if sensory_data is not None:
            current_temp = sensory_data.value
        else:
            # There is no sensoryData with the same name as the setpoint we are using, see
            # if we are using leavingWaterOffset, at that moment see if we have a
            # leavingWaterTemperature temperature
            lwsensor = self.sensory_data("leavingWaterTemperature")
            if self._setpoint == "leavingWaterOffset" and lwsensor is not None:
                current_temp = lwsensor.value
        _LOGGER.debug(
            "Device '%s' %s current temperature '%s'",
            self._device.name,
            self._setpoint,
            current_temp,
        )
        return current_temp

    def get_max_temp(self):
        """Return the maximum configurable temperature."""
        max_temp = None
        setpointdict = self.setpoint()
        max_temp = (
            setpointdict.max_value if setpointdict is not None else super().max_temp
        )
        _LOGGER.debug(
            "Device '%s' %s max temperature '%s'",
            self._device.name,
            self._setpoint,
            max_temp,
        )
        return max_temp

    def get_min_temp(self):
        """Return the minimum configurable temperature."""
        min_temp = None
        setpointdict = self.setpoint()
        min_temp = (
            setpointdict.min_value if setpointdict is not None else super().min_temp
        )
        _LOGGER.debug(
            "Device '%s' %s min temperature '%s'",
            self._device.name,
            self._setpoint,
            min_temp,
        )
        return min_temp

    def get_target_temperature(self):
        """Return the configured target temperature."""
        value = None
        setpointdict = self.setpoint()
        if setpointdict is not None:
            value = setpointdict.value
        _LOGGER.debug(
            "Device '%s' %s target temperature '%s'",
            self._device.name,
            self._setpoint,
            value,
        )
        return value

    def get_target_temperature_step(self):
        """Return the target temperature increment."""
        step_value = None
        setpointdict = self.setpoint()
        if setpointdict is not None:
            step_value = (
                setpointdict.step_value
                if setpointdict.step_value is not None
                else super().target_temperature_step
            )
        _LOGGER.debug(
            "Device '%s' %s target temperature step '%s'",
            self._device.name,
            self._setpoint,
            step_value,
        )
        return step_value

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the HVAC mode and/or target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

        if ATTR_TEMPERATURE in kwargs:
            value = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug(
                "Device '%s' request to set temperature to '%s'",
                self._device.name,
                value,
            )
            if self._attr_target_temperature != value:
                operationmode = self.operation_mode()
                if operationmode is not None:
                    omv = operationmode.value
                    res = await self._device.patch(
                        self._device.id,
                        self._embedded_id,
                        "temperatureControl",
                        f"/operationModes/{omv}/setpoints/{self._setpoint}",
                        value,
                    )
                    # When updating the value to the daikin cloud worked update our local cached version
                    if res:
                        setpointdict = self.setpoint(omv)
                        if setpointdict is not None:
                            setpointdict.value = value
                            self._attr_target_temperature = value
                            self.coordinator.async_update_listeners()
                    else:
                        _LOGGER.warning(
                            "Device '%s' problem setting temperature to '%s'",
                            self._device.name,
                            value,
                        )
                        self._raise_command_failed("set the temperature")

    def get_hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode."""
        mode = HVACMode.OFF
        operationmode = self.operation_mode()
        cc = self.climate_control()
        if cc is not None:
            onoff = cc.on_off_mode
            if onoff is not None and onoff.value != "off" and operationmode is not None:
                mode = operationmode.value
            _LOGGER.debug(
                "Device '%s' %s hvac mode '%s'",
                self._device.name,
                self._setpoint,
                mode,
            )
        return DAIKIN_HVAC_TO_HA.get(mode)

    def get_hvac_modes(self):
        """Return the list of available HVAC modes."""
        modes = [HVACMode.OFF]
        operationmode = self.operation_mode()
        if operationmode is not None:
            if operationmode.settable:
                for mode in operationmode.values or []:
                    ha_mode = DAIKIN_HVAC_TO_HA.get(mode)
                    if ha_mode is not None and ha_mode not in modes:
                        modes.append(ha_mode)
            currentmode = operationmode.value
            ha_currentmode = DAIKIN_HVAC_TO_HA.get(currentmode)
            if ha_currentmode is not None and ha_currentmode not in modes:
                modes.append(ha_currentmode)
        return modes

    def _native_hvac_mode(self, hvac_mode: HVACMode) -> str | None:
        """Return an advertised native mode for a requested HVAC mode."""
        operation_mode = self.operation_mode()
        if operation_mode is None:
            return None

        if DAIKIN_HVAC_TO_HA.get(operation_mode.value) == hvac_mode:
            return operation_mode.value

        if not operation_mode.settable:
            return None

        return next(
            (
                mode
                for mode in operation_mode.values or []
                if DAIKIN_HVAC_TO_HA.get(mode) == hvac_mode
            ),
            None,
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug(
            "Device '%s' request to set hvac_mode to '%s'",
            self._device.name,
            hvac_mode,
        )

        # First determine the new settings for onOffMode/operationMode
        on_off_mode = None
        if hvac_mode == HVACMode.OFF:
            if self.hvac_mode != HVACMode.OFF:
                on_off_mode = "off"
        elif self.hvac_mode == HVACMode.OFF:
            on_off_mode = "on"

        cc = self.climate_control()

        # Only set the on/off to Daikin when we need to change it
        if on_off_mode is not None:
            if not await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", on_off_mode
            ):
                _LOGGER.warning(
                    "Device '%s' problem setting onOffMode to '%s'",
                    self._device.name,
                    on_off_mode,
                )
                self._raise_command_failed("set the HVAC mode")
            cc = self.climate_control()
            if cc is not None and cc.on_off_mode is not None:
                cc.on_off_mode.value = on_off_mode
                # Publish the confirmed power change before a subsequent
                # operation-mode write, which may be rejected by the cloud.
                self.update_state()
                self.coordinator.async_update_listeners()

        operation_mode = (
            self._native_hvac_mode(hvac_mode) if hvac_mode != HVACMode.OFF else None
        )

        # Only set the advertised operationMode when it has changed.
        if (
            operation_mode is not None
            and cc.operation_mode is not None
            and operation_mode != cc.operation_mode.value
        ):
            if not await self._device.patch(
                self._device.id,
                self._embedded_id,
                "operationMode",
                "",
                operation_mode,
            ):
                _LOGGER.warning(
                    "Device '%s' problem setting operationMode to '%s'",
                    self._device.name,
                    operation_mode,
                )
                self._raise_command_failed("set the HVAC mode")
            cc = self.climate_control()
            if cc is not None and cc.operation_mode is not None:
                cc.operation_mode.value = operation_mode
            # When switching HVAC mode it could be that we can set min/max/target/etc
            # which we couldn't set with a previous HVAC mode.
            self.update_state()
            self.coordinator.async_update_listeners()

    def get_fan_mode(self):
        """Return the active fan mode."""
        fan_operation = self.fan_operation()
        if fan_operation is None or fan_operation.fan_speed is None:
            return None
        fan_speed = fan_operation.fan_speed
        mode = fan_speed.current_mode.value
        if (
            mode == FANMODE_FIXED
            and fan_speed.modes
            and FANMODE_FIXED in fan_speed.modes
        ):
            mode = str(fan_speed.modes[FANMODE_FIXED].value)
        return self.get_homekit_fan_mode(fan_speed, mode)

    def get_fan_modes(self):
        """Return available fan modes."""
        fan_operation = self.fan_operation()
        if fan_operation is None or fan_operation.fan_speed is None:
            return []
        fan_speed = fan_operation.fan_speed
        fan_modes: list[str] = []
        for mode in fan_speed.current_mode.values or []:
            if (
                mode == FANMODE_FIXED
                and fan_speed.modes
                and FANMODE_FIXED in fan_speed.modes
            ):
                fixed = fan_speed.modes[FANMODE_FIXED]
                if (
                    fixed.min_value is not None
                    and fixed.max_value is not None
                    and fixed.step_value is not None
                ):
                    fan_modes.extend(
                        str(value)
                        for value in range(
                            int(fixed.min_value),
                            int(fixed.max_value) + 1,
                            int(fixed.step_value),
                        )
                    )
            else:
                fan_modes.append(mode)
        for alias in self.homekit_fan_mode_aliases(fan_speed):
            if alias not in fan_modes:
                fan_modes.append(alias)
        return fan_modes

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        requested_fan_mode = str(fan_mode)
        fan_operation = self.fan_operation()
        cc = self.climate_control()
        if (
            fan_operation is None
            or fan_operation.fan_speed is None
            or cc is None
            or cc.operation_mode is None
        ):
            return
        fan_speed = fan_operation.fan_speed
        operation_mode = cc.operation_mode.value
        fan_mode = self.resolve_homekit_fan_mode_alias(fan_speed, requested_fan_mode)
        if fan_mode.isnumeric():
            if fan_speed.current_mode.value != FANMODE_FIXED:
                if not await self._device.patch(
                    self._device.id,
                    self._embedded_id,
                    "fanControl",
                    f"/operationModes/{operation_mode}/fanSpeed/currentMode",
                    FANMODE_FIXED,
                ):
                    self._raise_command_failed("set the fan mode")
                fan_operation = self.fan_operation(operation_mode)
                if fan_operation is None or fan_operation.fan_speed is None:
                    return
                fan_speed = fan_operation.fan_speed
                fan_speed.current_mode.value = FANMODE_FIXED
                # The fan is already in fixed mode even if the following speed
                # write fails, so publish this confirmed intermediate state.
                self._attr_fan_mode = self.get_fan_mode()
                self.coordinator.async_update_listeners()
            fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
            new_fixed_mode = int(fan_mode)
            if fixed is not None and fixed.value != new_fixed_mode:
                if not await self._device.patch(
                    self._device.id,
                    self._embedded_id,
                    "fanControl",
                    f"/operationModes/{operation_mode}/fanSpeed/modes/fixed",
                    new_fixed_mode,
                ):
                    self._raise_command_failed("set the fan mode")
                fan_operation = self.fan_operation(operation_mode)
                if fan_operation is None or fan_operation.fan_speed is None:
                    return
                fan_speed = fan_operation.fan_speed
                fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
                if fixed is None:
                    return
                fixed.value = new_fixed_mode
        elif fan_speed.current_mode.value != fan_mode:
            if not await self._device.patch(
                self._device.id,
                self._embedded_id,
                "fanControl",
                f"/operationModes/{operation_mode}/fanSpeed/currentMode",
                fan_mode,
            ):
                self._raise_command_failed("set the fan mode")
            fan_operation = self.fan_operation(operation_mode)
            if fan_operation is None or fan_operation.fan_speed is None:
                return
            fan_speed = fan_operation.fan_speed
            fan_speed.current_mode.value = fan_mode

        self._attr_fan_mode = self.get_fan_mode()
        self.coordinator.async_update_listeners()

    def __get_swing_mode(self, direction):
        """Return current swing mode for an axis."""
        fan_operation = self.fan_operation()
        if fan_operation is None or fan_operation.fan_direction is None:
            return ""
        axis = getattr(fan_operation.fan_direction, direction)
        return axis.current_mode.value.lower() if axis is not None else ""

    def get_swing_mode(self):
        """Return the vertical swing mode."""
        return self.__get_swing_mode("vertical")

    def get_swing_horizontal_mode(self):
        """Return the horizontal swing mode."""
        return self.__get_swing_mode("horizontal")

    def __get_swing_modes(self, direction):
        """Return supported swing modes for an axis."""
        fan_operation = self.fan_operation()
        if fan_operation is None or fan_operation.fan_direction is None:
            return []
        axis = getattr(fan_operation.fan_direction, direction)
        if axis is None:
            return []
        return [mode.lower() for mode in axis.current_mode.values or []]

    def get_swing_modes(self):
        """Return the supported vertical swing modes."""
        return self.__get_swing_modes("vertical")

    def get_swing_horizontal_modes(self):
        """Return the supported horizontal swing modes."""
        return self.__get_swing_modes("horizontal")

    async def __set_swing(self, direction, swing_mode):
        """Set a fan-direction mode."""
        fan_operation = self.fan_operation()
        cc = self.climate_control()
        if (
            fan_operation is None
            or fan_operation.fan_direction is None
            or cc is None
            or cc.operation_mode is None
        ):
            return False
        axis = getattr(fan_operation.fan_direction, direction)
        if axis is None:
            return False
        new_mode = next(
            (
                mode
                for mode in axis.current_mode.values or []
                if swing_mode == mode.lower()
            ),
            "stop",
        )
        operation_mode = cc.operation_mode.value
        result = await self._device.patch(
            self._device.id,
            self._embedded_id,
            "fanControl",
            f"/operationModes/{operation_mode}/fanDirection/{direction}/currentMode",
            new_mode,
        )
        if result:
            fan_operation = self.fan_operation(operation_mode)
            if fan_operation is not None and fan_operation.fan_direction is not None:
                axis = getattr(fan_operation.fan_direction, direction)
                if axis is not None:
                    axis.current_mode.value = new_mode
        return result

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode."""
        res = True
        if self.swing_mode != swing_mode:
            res = await self.__set_swing("vertical", swing_mode)

            if res is True:
                self._attr_swing_mode = swing_mode
                self.coordinator.async_update_listeners()
            else:
                self._raise_command_failed("set the swing mode")
        else:
            _LOGGER.debug(
                "Device '%s' request to set vertical swing mode '%s' ignored already set",
                self._device.name,
                swing_mode,
            )

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal swing mode."""
        res = True
        if self.swing_horizontal_mode != swing_horizontal_mode:
            res = await self.__set_swing("horizontal", swing_horizontal_mode)

            if res is True:
                self._attr_swing_horizontal_mode = swing_horizontal_mode
                self.coordinator.async_update_listeners()
            else:
                self._raise_command_failed("set the horizontal swing mode")
        else:
            _LOGGER.debug(
                "Device '%s' request to set horizontal swing mode '%s' ignored already set",
                self._device.name,
                swing_horizontal_mode,
            )

    def get_preset_mode(self):
        """Return the active preset mode."""
        for mode in PRESET_MODES:
            preset = self.preset_characteristic(HA_PRESET_TO_DAIKIN[mode])
            if preset is None:
                continue
            if mode == PRESET_AWAY:
                if preset.value.enabled:
                    return mode
            elif preset.value == "on":
                return mode
        return PRESET_NONE

    async def _async_disable_preset_mode(self, preset_mode) -> bool:
        """Disable the current Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if preset_mode == PRESET_AWAY:
            result = await self._device.post(
                self._device.id, self._embedded_id, "holiday-mode", {"enabled": False}
            )
        else:
            result = await self._device.patch(
                self._device.id, self._embedded_id, daikin_mode, "", "off"
            )
        if not result:
            _LOGGER.warning(
                "Device '%s' problem setting %s to off", self._device.name, daikin_mode
            )
        else:
            preset = self.preset_characteristic(daikin_mode)
            if preset_mode == PRESET_AWAY and preset is not None:
                preset.value.enabled = False
            elif preset is not None:
                preset.value = "off"
        return result

    async def _async_enable_preset_mode(self, preset_mode) -> bool:
        """Enable the requested Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if self.hvac_mode == HVACMode.OFF and preset_mode == PRESET_BOOST:
            await self.async_turn_on()
            if self.hvac_mode == HVACMode.OFF:
                return False
        if preset_mode == PRESET_AWAY:
            today = dt_util.now().date()
            value = {
                "enabled": True,
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=60)).isoformat(),
            }
            result = await self._device.post(
                self._device.id, self._embedded_id, "holiday-mode", value
            )
        else:
            result = await self._device.patch(
                self._device.id, self._embedded_id, daikin_mode, "", "on"
            )
        if not result:
            _LOGGER.warning(
                "Device '%s' problem setting %s to on", self._device.name, daikin_mode
            )
        else:
            preset = self.preset_characteristic(daikin_mode)
            if preset_mode == PRESET_AWAY and preset is not None:
                preset.value.enabled = True
            elif preset is not None:
                preset.value = "on"
        return result

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the active preset mode."""
        _LOGGER.debug(
            "Device '%s' request set preset mode %s", self._device.name, preset_mode
        )
        if self.preset_mode != PRESET_NONE:
            if not await self._async_disable_preset_mode(self.preset_mode):
                self._raise_command_failed("set the preset mode")
            self.update_state()
            self.coordinator.async_update_listeners()

        if preset_mode != PRESET_NONE:
            if not await self._async_enable_preset_mode(preset_mode):
                self._raise_command_failed("set the preset mode")
            self.update_state()
            self.coordinator.async_update_listeners()

    def get_preset_modes(self):
        """Return supported preset modes."""
        supported = [PRESET_NONE]
        supported.extend(
            mode
            for mode in PRESET_MODES
            if self.preset_characteristic(HA_PRESET_TO_DAIKIN[mode]) is not None
        )
        supported.sort()
        return supported

    @override
    async def async_turn_on(self) -> None:
        """Turn device CLIMATE on."""
        _LOGGER.debug("Device '%s' request to turn on", self._device.name)
        cc = self.climate_control()
        result = True
        if cc.on_off_mode is not None and cc.on_off_mode.value == "off":
            result &= await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", "on"
            )
            if result is False:
                _LOGGER.error(
                    "Device '%s' problem setting onOffMode to on", self._device.name
                )
                self._raise_command_failed("turn on")
            else:
                cc = self.climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "on"
                self._attr_hvac_mode = self.get_hvac_mode()
                self.coordinator.async_update_listeners()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn on ignored because device is already on",
                self._device.name,
            )

    @override
    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        _LOGGER.debug("Device '%s' request to turn off", self._device.name)
        cc = self.climate_control()
        result = True
        if cc.on_off_mode is not None and cc.on_off_mode.value == "on":
            result &= await self._device.patch(
                self._device.id, self._embedded_id, "onOffMode", "", "off"
            )
            if result is False:
                _LOGGER.error(
                    "Device '%s' problem setting onOffMode to off", self._device.name
                )
                self._raise_command_failed("turn off")
            else:
                cc = self.climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "off"
                self._attr_hvac_mode = self.get_hvac_mode()
                self.coordinator.async_update_listeners()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn off ignored because device is already off",
                self._device.name,
            )
