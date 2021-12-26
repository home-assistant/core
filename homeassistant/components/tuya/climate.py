"""Support for Tuya Climate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import EnumTypeData, IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

TUYA_HVAC_TO_HA = {
    "auto": HVAC_MODE_HEAT_COOL,
    "cold": HVAC_MODE_COOL,
    "freeze": HVAC_MODE_COOL,
    "heat": HVAC_MODE_HEAT,
    "hot": HVAC_MODE_HEAT,
    "manual": HVAC_MODE_HEAT_COOL,
    "wet": HVAC_MODE_DRY,
    "wind": HVAC_MODE_FAN_ONLY,
}


@dataclass
class TuyaClimateSensorDescriptionMixin:
    """Define an entity description mixin for climate entities."""

    switch_only_hvac_mode: str


@dataclass
class TuyaClimateEntityDescription(
    ClimateEntityDescription, TuyaClimateSensorDescriptionMixin
):
    """Describe an Tuya climate entity."""


CLIMATE_DESCRIPTIONS: dict[str, TuyaClimateEntityDescription] = {
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": TuyaClimateEntityDescription(
        key="kt",
        switch_only_hvac_mode=HVAC_MODE_COOL,
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46epy4j82
    "qn": TuyaClimateEntityDescription(
        key="qn",
        switch_only_hvac_mode=HVAC_MODE_HEAT,
    ),
    # Thermostat
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf45ld5l0t9
    "wk": TuyaClimateEntityDescription(
        key="wk",
        switch_only_hvac_mode=HVAC_MODE_HEAT_COOL,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya climate."""
        entities: list[TuyaClimateEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in CLIMATE_DESCRIPTIONS:
                entities.append(
                    TuyaClimateEntity(
                        device,
                        hass_data.device_manager,
                        CLIMATE_DESCRIPTIONS[device.category],
                    )
                )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaClimateEntity(TuyaEntity, ClimateEntity):
    """Tuya Climate Device."""

    _current_humidity_dpcode: DPCode | None = None
    _current_humidity_type: IntegerTypeData | None = None
    _current_temperature_dpcode: DPCode | None = None
    _current_temperature_type: IntegerTypeData | None = None
    _hvac_to_tuya: dict[str, str]
    _set_humidity_dpcode: DPCode | None = None
    _set_humidity_type: IntegerTypeData | None = None
    _set_temperature_dpcode: DPCode | None = None
    _set_temperature_type: IntegerTypeData | None = None
    entity_description: TuyaClimateEntityDescription

    def __init__(  # noqa: C901
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaClimateEntityDescription,
    ) -> None:
        """Determine which values to use."""
        self._attr_target_temperature_step = 1.0
        self._attr_supported_features = 0
        self.entity_description = description

        super().__init__(device, device_manager)

        # If both temperature values for celsius and fahrenheit are present,
        # use whatever the device is set to, with a fallback to celsius.
        if all(
            dpcode in device.status
            for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_CURRENT_F)
        ) or all(
            dpcode in device.status for dpcode in (DPCode.TEMP_SET, DPCode.TEMP_SET_F)
        ):
            self._attr_temperature_unit = TEMP_CELSIUS
            if any(
                "f" in device.status.get(dpcode, "").lower()
                for dpcode in (DPCode.C_F, DPCode.TEMP_UNIT_CONVERT)
            ):
                self._attr_temperature_unit = TEMP_FAHRENHEIT

        # If any DPCode handling celsius is present, use celsius.
        elif any(
            dpcode in device.status for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_SET)
        ):
            self._attr_temperature_unit = TEMP_CELSIUS

        # If any DPCode handling fahrenheit is present, use celsius.
        elif any(
            dpcode in device.status
            for dpcode in (DPCode.TEMP_CURRENT_F, DPCode.TEMP_SET_F)
        ):
            self._attr_temperature_unit = TEMP_FAHRENHEIT

        # Determine dpcode to use for setting temperature
        if all(
            dpcode in device.status for dpcode in (DPCode.TEMP_SET, DPCode.TEMP_SET_F)
        ):
            self._set_temperature_dpcode = DPCode.TEMP_SET
            if self._attr_temperature_unit == TEMP_FAHRENHEIT:
                self._set_temperature_dpcode = DPCode.TEMP_SET_F
        elif DPCode.TEMP_SET in device.status:
            self._set_temperature_dpcode = DPCode.TEMP_SET
        elif DPCode.TEMP_SET_F in device.status:
            self._set_temperature_dpcode = DPCode.TEMP_SET_F

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if (
            self._set_temperature_dpcode
            and self._set_temperature_dpcode in device.status_range
        ):
            type_data = IntegerTypeData.from_json(
                device.status_range[self._set_temperature_dpcode].values
            )
            self._attr_supported_features |= SUPPORT_TARGET_TEMPERATURE
            self._set_temperature_type = type_data
            self._attr_max_temp = type_data.max_scaled
            self._attr_min_temp = type_data.min_scaled
            self._attr_target_temperature_step = type_data.step_scaled

        # Determine dpcode to use for getting the current temperature
        if all(
            dpcode in device.status
            for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_CURRENT_F)
        ):
            self._current_temperature_dpcode = DPCode.TEMP_CURRENT
            if self._attr_temperature_unit == TEMP_FAHRENHEIT:
                self._current_temperature_dpcode = DPCode.TEMP_CURRENT_F
        elif DPCode.TEMP_CURRENT in device.status:
            self._current_temperature_dpcode = DPCode.TEMP_CURRENT
        elif DPCode.TEMP_CURRENT_F in device.status:
            self._current_temperature_dpcode = DPCode.TEMP_CURRENT_F

        # If we have a current temperature dpcode, get the integer type data
        if (
            self._current_temperature_dpcode
            and self._current_temperature_dpcode in device.status_range
        ):
            self._current_temperature_type = IntegerTypeData.from_json(
                device.status_range[self._current_temperature_dpcode].values
            )

        # Determine HVAC modes
        self._attr_hvac_modes = []
        self._hvac_to_tuya = {}
        if DPCode.MODE in device.function:
            data_type = EnumTypeData.from_json(device.function[DPCode.MODE].values)
            self._attr_hvac_modes = [HVAC_MODE_OFF]
            for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
                if tuya_mode in data_type.range:
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
        elif DPCode.SWITCH in device.function:
            self._attr_hvac_modes = [
                HVAC_MODE_OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine dpcode to use for setting the humidity
        if (
            DPCode.HUMIDITY_SET in device.status
            and DPCode.HUMIDITY_SET in device.status_range
        ):
            self._attr_supported_features |= SUPPORT_TARGET_HUMIDITY
            self._set_humidity_dpcode = DPCode.HUMIDITY_SET
            type_data = IntegerTypeData.from_json(
                device.status_range[DPCode.HUMIDITY_SET].values
            )
            self._set_humidity_type = type_data
            self._attr_min_humidity = int(type_data.min_scaled)
            self._attr_max_humidity = int(type_data.max_scaled)

        # Determine dpcode to use for getting the current humidity
        if (
            DPCode.HUMIDITY_CURRENT in device.status
            and DPCode.HUMIDITY_CURRENT in device.status_range
        ):
            self._current_humidity_dpcode = DPCode.HUMIDITY_CURRENT
            self._current_humidity_type = IntegerTypeData.from_json(
                device.status_range[DPCode.HUMIDITY_CURRENT].values
            )

        # Determine dpcode to use for getting the current humidity
        if (
            DPCode.HUMIDITY_CURRENT in device.status
            and DPCode.HUMIDITY_CURRENT in device.status_range
        ):
            self._current_humidity_dpcode = DPCode.HUMIDITY_CURRENT
            self._current_humidity_type = IntegerTypeData.from_json(
                device.status_range[DPCode.HUMIDITY_CURRENT].values
            )

        # Determine fan modes
        if (
            DPCode.FAN_SPEED_ENUM in device.status
            and DPCode.FAN_SPEED_ENUM in device.function
        ):
            self._attr_supported_features |= SUPPORT_FAN_MODE
            self._attr_fan_modes = EnumTypeData.from_json(
                device.status_range[DPCode.FAN_SPEED_ENUM].values
            ).range

        # Determine swing modes
        if any(
            dpcode in device.function
            for dpcode in (
                DPCode.SHAKE,
                DPCode.SWING,
                DPCode.SWITCH_HORIZONTAL,
                DPCode.SWITCH_VERTICAL,
            )
        ):
            self._attr_supported_features |= SUPPORT_SWING_MODE
            self._attr_swing_modes = [SWING_OFF]
            if any(
                dpcode in device.function for dpcode in (DPCode.SHAKE, DPCode.SWING)
            ):
                self._attr_swing_modes.append(SWING_ON)

            if DPCode.SWITCH_HORIZONTAL in device.function:
                self._attr_swing_modes.append(SWING_HORIZONTAL)

            if DPCode.SWITCH_VERTICAL in device.function:
                self._attr_swing_modes.append(SWING_VERTICAL)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        commands = [{"code": DPCode.SWITCH, "value": hvac_mode != HVAC_MODE_OFF}]
        if hvac_mode in self._hvac_to_tuya:
            commands.append(
                {"code": DPCode.MODE, "value": self._hvac_to_tuya[hvac_mode]}
            )
        self._send_command(commands)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._send_command([{"code": DPCode.FAN_SPEED_ENUM, "value": fan_mode}])

    def set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        if self._set_humidity_dpcode is None or self._set_humidity_type is None:
            raise RuntimeError(
                "Cannot set humidity, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_humidity_dpcode,
                    "value": self._set_humidity_type.scale_value_back(humidity),
                }
            ]
        )

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        # The API accepts these all at once and will ignore the codes
        # that don't apply to the device being controlled.
        self._send_command(
            [
                {
                    "code": DPCode.SHAKE,
                    "value": swing_mode == SWING_ON,
                },
                {
                    "code": DPCode.SWING,
                    "value": swing_mode == SWING_ON,
                },
                {
                    "code": DPCode.SWITCH_VERTICAL,
                    "value": swing_mode in (SWING_BOTH, SWING_VERTICAL),
                },
                {
                    "code": DPCode.SWITCH_HORIZONTAL,
                    "value": swing_mode in (SWING_BOTH, SWING_HORIZONTAL),
                },
            ]
        )

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self._set_temperature_dpcode is None or self._set_temperature_type is None:
            raise RuntimeError(
                "Cannot set target temperature, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_temperature_dpcode,
                    "value": round(
                        self._set_temperature_type.scale_value_back(
                            kwargs["temperature"]
                        )
                    ),
                }
            ]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (
            self._current_temperature_dpcode is None
            or self._current_temperature_type is None
        ):
            return None

        temperature = self.device.status.get(self._current_temperature_dpcode)
        if temperature is None:
            return None

        return self._current_temperature_type.scale_value(temperature)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if self._current_humidity_dpcode is None or self._current_humidity_type is None:
            return None

        humidity = self.device.status.get(self._current_humidity_dpcode)
        if humidity is None:
            return None

        return round(self._current_humidity_type.scale_value(humidity))

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        if self._set_temperature_dpcode is None or self._set_temperature_type is None:
            return None

        temperature = self.device.status.get(self._set_temperature_dpcode)
        if temperature is None:
            return None

        return self._set_temperature_type.scale_value(temperature)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        if self._set_humidity_dpcode is None or self._set_humidity_type is None:
            return None

        humidity = self.device.status.get(self._set_humidity_dpcode)
        if humidity is None:
            return None

        return round(self._set_humidity_type.scale_value(humidity))

    @property
    def hvac_mode(self) -> str:
        """Return hvac mode."""
        # If the switch off, hvac mode is off as well. Unless the switch
        # the switch is on or doesn't exists of course...
        if not self.device.status.get(DPCode.SWITCH, True):
            return HVAC_MODE_OFF

        if DPCode.MODE not in self.device.function:
            if self.device.status.get(DPCode.SWITCH, False):
                return self.entity_description.switch_only_hvac_mode
            return HVAC_MODE_OFF

        if self.device.status.get(DPCode.MODE) is not None:
            return TUYA_HVAC_TO_HA[self.device.status[DPCode.MODE]]
        return HVAC_MODE_OFF

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self.device.status.get(DPCode.FAN_SPEED_ENUM)

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        if any(
            self.device.status.get(dpcode) for dpcode in (DPCode.SHAKE, DPCode.SWING)
        ):
            return SWING_ON

        horizontal = self.device.status.get(DPCode.SWITCH_HORIZONTAL)
        vertical = self.device.status.get(DPCode.SWITCH_VERTICAL)
        if horizontal and vertical:
            return SWING_BOTH
        if horizontal:
            return SWING_HORIZONTAL
        if vertical:
            return SWING_VERTICAL

        return SWING_OFF

    def turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if DPCode.SWITCH in self.device.function:
            self._send_command([{"code": DPCode.SWITCH, "value": True}])
            return

        # Fake turn on
        for mode in (HVAC_MODE_HEAT_COOL, HVAC_MODE_HEAT, HVAC_MODE_COOL):
            if mode not in self.hvac_modes:
                continue
            self.set_hvac_mode(mode)
            break

    def turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if DPCode.SWITCH in self.device.function:
            self._send_command([{"code": DPCode.SWITCH, "value": False}])
            return

        # Fake turn off
        if HVAC_MODE_OFF in self.hvac_modes:
            self.set_hvac_mode(HVAC_MODE_OFF)
