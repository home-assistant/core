"""Midea Climate entries."""

from dataclasses import dataclass
import logging
from typing import Any, cast, override

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes, MideaACDevice
from midealocal.devices.c3 import MideaC3Device
from midealocal.devices.c3.const import DeviceAttributes as C3Attributes
from midealocal.devices.cc import DeviceAttributes as CCAttributes, MideaCCDevice
from midealocal.devices.cf import DeviceAttributes as CFAttributes, MideaCFDevice
from midealocal.devices.fb import DeviceAttributes as FBAttributes, MideaFBDevice

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, FanSpeed
from .entity import MideaEntity, MideaLanConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


TEMPERATURE_MAX = 30
TEMPERATURE_MIN = 16

TEMPERATURE_MAX_C3 = 60
TEMPERATURE_MIN_C3 = 5

FAN_SILENT = "silent"
FAN_FULL_SPEED = "full"

FEATURES_TARGET_AND_POWER = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)

type MideaClimateDevice = (
    MideaACDevice | MideaCCDevice | MideaCFDevice | MideaC3Device | MideaFBDevice
)


@dataclass(kw_only=True, frozen=True)
class MideaClimateEntityDescription(ClimateEntityDescription):
    """Description for a Midea climate entity."""

    models: list[DeviceType]
    zone: int | None = None


CLIMATE_ENTITIES: list[MideaClimateEntityDescription] = [
    MideaClimateEntityDescription(
        key="climate",
        models=[DeviceType.AC, DeviceType.CC, DeviceType.CF, DeviceType.FB],
    ),
    MideaClimateEntityDescription(
        key="climate_zone1",
        models=[DeviceType.C3],
        translation_key="climate_zone1",
        zone=0,
    ),
    MideaClimateEntityDescription(
        key="climate_zone2",
        models=[DeviceType.C3],
        translation_key="climate_zone2",
        zone=1,
        entity_registry_enabled_default=False,
    ),
]

_PRESET_TO_ATTR: dict[str, str] = {
    PRESET_AWAY: "frost_protect",
    PRESET_COMFORT: "comfort_mode",
    PRESET_SLEEP: "sleep_mode",
    PRESET_ECO: "eco_mode",
    PRESET_BOOST: "boost_mode",
}

_ATTR_TO_PRESET: dict[str, str] = {v: k for k, v in _PRESET_TO_ATTR.items()}

_SWING_MODE_MAP: dict[str, tuple[bool, bool]] = {
    SWING_OFF: (False, False),
    SWING_VERTICAL: (True, False),
    SWING_HORIZONTAL: (False, True),
    SWING_BOTH: (True, True),
}

_SWING_STATE_MAP: dict[tuple[bool, bool], str] = {
    v: k for k, v in _SWING_MODE_MAP.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entries."""
    device = config_entry.runtime_data

    entities: list[MideaClimate] = []
    for description in CLIMATE_ENTITIES:
        if device.device_type not in description.models:
            continue
        if device.device_type == DeviceType.AC:
            entities.append(MideaACClimate(cast(MideaACDevice, device), description))
        elif device.device_type == DeviceType.CC:
            entities.append(MideaCCClimate(cast(MideaCCDevice, device), description))
        elif device.device_type == DeviceType.CF:
            entities.append(MideaCFClimate(cast(MideaCFDevice, device), description))
        elif device.device_type == DeviceType.C3 and description.zone is not None:
            entities.append(
                MideaC3Climate(
                    cast(MideaC3Device, device), description, description.zone
                )
            )
        elif device.device_type == DeviceType.FB:
            entities.append(MideaFBClimate(cast(MideaFBDevice, device), description))
    async_add_entities(entities)


class MideaClimate(MideaEntity, ClimateEntity):
    """Midea Climate Entries Base Class."""

    _device: MideaClimateDevice

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_max_temp = TEMPERATURE_MAX
    _attr_min_temp = TEMPERATURE_MIN
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _zone: int | None = None

    def __init__(
        self,
        device: MideaClimateDevice,
        description: MideaClimateEntityDescription,
    ) -> None:
        """Midea Climate entity init."""
        super().__init__(device, description.key)
        self.entity_description = description

    def _float_attribute(self, attr: str) -> float | None:
        """Return a device attribute as float, if convertible."""
        value = self._device.get_attribute(attr)
        if not isinstance(value, (int, float, str)):
            return None
        return float(value)

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Midea Climate hvac mode."""
        power = self._device.get_attribute(attr="power")
        if not isinstance(power, bool):
            return None
        if not power:
            return HVACMode.OFF

        mode = self._device.get_attribute("mode")
        if isinstance(mode, int):
            return self._protocol_mode_to_hvac(mode)
        return None

    def _protocol_mode_to_hvac(self, mode: int) -> HVACMode | None:
        """Convert protocol mode value to Home Assistant HVAC mode."""
        if 1 <= mode < len(self.hvac_modes):
            return self.hvac_modes[mode]
        return None

    def _hvac_to_protocol_mode(self, hvac_mode: HVACMode) -> int:
        """Convert Home Assistant HVAC mode to protocol mode value."""
        return self.hvac_modes.index(hvac_mode)

    @property
    @override
    def target_temperature(self) -> float | None:
        """Midea Climate target temperature."""
        return self._float_attribute("target_temperature")

    @property
    @override
    def current_temperature(self) -> float | None:
        """Midea Climate current temperature."""
        return self._float_attribute("indoor_temperature")

    @property
    @override
    def preset_mode(self) -> str | None:
        """Midea Climate preset mode."""
        for attr, preset in _ATTR_TO_PRESET.items():
            if self._device.get_attribute(attr):
                return preset

        return PRESET_NONE

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea Climate turn on."""
        self._device.set_attribute(attr="power", value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea Climate turn off."""
        self._device.set_attribute(attr="power", value=False)

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Midea Climate set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = kwargs[ATTR_TEMPERATURE]
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            mode = None
            if hvac_mode:
                if hvac_mode not in self.hvac_modes:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="unsupported_hvac_mode",
                        translation_placeholders={"hvac_mode": hvac_mode},
                    )
                mode = self.hvac_modes.index(hvac_mode)
            self._device.set_target_temperature(
                target_temperature=temperature,
                mode=mode,
                zone=self._zone,
            )

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self._device.set_attribute(
                attr="mode",
                value=self._hvac_to_protocol_mode(hvac_mode),
            )

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Midea Climate set preset mode."""
        if new_attr := _PRESET_TO_ATTR.get(preset_mode):
            self._device.set_attribute(attr=new_attr, value=True)
            return
        old_mode = self.preset_mode
        old_attr = _PRESET_TO_ATTR.get(old_mode) if isinstance(old_mode, str) else None
        if old_attr:
            self._device.set_attribute(attr=old_attr, value=False)


class MideaACClimate(MideaClimate):
    """Midea AC Climate Entries."""

    _device: MideaACDevice

    _fan_thresholds: tuple[tuple[int, str], ...] = (
        (FanSpeed.AUTO, FAN_AUTO),
        (FanSpeed.FULL_SPEED, FAN_FULL_SPEED),
        (FanSpeed.HIGH, FAN_HIGH),
        (FanSpeed.MEDIUM, FAN_MEDIUM),
        (FanSpeed.LOW, FAN_LOW),
    )

    _fan_speeds: dict[str, int] = {
        FAN_SILENT: 20,
        FAN_LOW: 40,
        FAN_MEDIUM: 60,
        FAN_HIGH: 80,
        FAN_FULL_SPEED: 100,
        FAN_AUTO: 102,
    }
    _attr_fan_modes: list[str] = [
        FAN_SILENT,
        FAN_LOW,
        FAN_MEDIUM,
        FAN_HIGH,
        FAN_FULL_SPEED,
        FAN_AUTO,
    ]

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
    ]
    _attr_swing_modes: list[str] = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
    _attr_preset_modes = [
        PRESET_NONE,
        PRESET_COMFORT,
        PRESET_ECO,
        PRESET_BOOST,
        PRESET_SLEEP,
        PRESET_AWAY,
    ]

    def __init__(
        self,
        device: MideaACDevice,
        description: MideaClimateEntityDescription,
    ) -> None:
        """Midea AC Climate entity init."""
        super().__init__(device, description)
        self._attr_target_temperature_step = float(
            PRECISION_WHOLE if self._device.temperature_step == 1 else PRECISION_HALVES,
        )

    @property
    @override
    def min_temp(self) -> float:
        """Midea AC Climate min temperature."""
        min_temperature = self._float_attribute(ACAttributes.min_temperature)
        if min_temperature is None:
            return float(TEMPERATURE_MIN)
        return min_temperature

    @property
    @override
    def max_temp(self) -> float:
        """Midea AC Climate max temperature."""
        max_temperature = self._float_attribute(ACAttributes.max_temperature)
        if max_temperature is None:
            return float(TEMPERATURE_MAX)
        return max_temperature

    @property
    @override
    def fan_mode(self) -> str | None:
        """Midea AC Climate fan mode."""
        fan_speed = self._device.get_attribute(ACAttributes.fan_speed)
        if not isinstance(fan_speed, int):
            return None
        for threshold, mode in self._fan_thresholds:
            if fan_speed > threshold:
                return mode
        return FAN_SILENT

    @property
    @override
    def swing_mode(self) -> str | None:
        """Midea AC Climate swing mode."""
        vertical = bool(self._device.get_attribute(ACAttributes.swing_vertical))
        horizontal = bool(self._device.get_attribute(ACAttributes.swing_horizontal))
        return _SWING_STATE_MAP.get((vertical, horizontal))

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return the current indoor humidity, or None if unavailable."""
        raw = self._device.get_attribute(ACAttributes.indoor_humidity)
        # Some devices report invalid values (0 or 0xFF) for this sensor
        # so filter those out and return None instead.
        if isinstance(raw, (int, float)) and raw not in {0, 0xFF}:
            return float(raw)
        return None

    @override
    def set_fan_mode(self, fan_mode: str) -> None:
        """Midea AC Climate set fan mode."""
        fan_speed = self._fan_speeds[fan_mode]
        self._device.set_attribute(attr=ACAttributes.fan_speed, value=fan_speed)

    @override
    def set_swing_mode(self, swing_mode: str) -> None:
        """Midea AC Climate set swing mode."""
        swing_vertical, swing_horizontal = _SWING_MODE_MAP.get(
            swing_mode, (False, False)
        )
        self._device.set_swing(
            swing_vertical=swing_vertical,
            swing_horizontal=swing_horizontal,
        )


class MideaCCClimate(MideaClimate):
    """Midea CC Climate Entries."""

    _device: MideaCCDevice

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_preset_modes = [PRESET_NONE, PRESET_SLEEP, PRESET_ECO]

    @property
    @override
    def fan_modes(self) -> list[str] | None:
        """Midea CC Climate fan modes."""
        return self._device.fan_modes

    @property
    @override
    def fan_mode(self) -> str | None:
        """Midea CC Climate fan mode."""
        fan_mode = self._device.get_attribute(CCAttributes.fan_speed)
        if not isinstance(fan_mode, str):
            return None
        return fan_mode

    @property
    @override
    def target_temperature_step(self) -> float | None:
        """Midea CC Climate target temperature step."""
        return self._float_attribute(CCAttributes.temperature_precision)

    @property
    @override
    def swing_mode(self) -> str | None:
        """Midea CC Climate swing mode."""
        swing = self._device.get_attribute(CCAttributes.swing)
        if not isinstance(swing, bool):
            return None
        return SWING_ON if swing else SWING_OFF

    @override
    def set_fan_mode(self, fan_mode: str) -> None:
        """Midea CC Climate set fan mode."""
        self._device.set_attribute(attr=CCAttributes.fan_speed, value=fan_mode)

    @override
    def set_swing_mode(self, swing_mode: str) -> None:
        """Midea CC Climate set swing mode."""
        self._device.set_attribute(
            attr=CCAttributes.swing,
            value=swing_mode == SWING_ON,
        )


class MideaCFClimate(MideaClimate):
    """Midea CF Climate Entries."""

    _device: MideaCFDevice

    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]
    _attr_target_temperature_step: float | None = PRECISION_WHOLE

    _attr_supported_features = FEATURES_TARGET_AND_POWER

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea CF Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            target_temperature = self.target_temperature or self.min_temp
            self._device.set_target_temperature(
                target_temperature=target_temperature,
                mode=self._hvac_to_protocol_mode(hvac_mode),
            )

    @property
    @override
    def min_temp(self) -> float:
        """Midea CF Climate min temperature."""
        min_temperature = self._float_attribute(CFAttributes.min_temperature)
        if min_temperature is None:
            return float(TEMPERATURE_MIN)
        return min_temperature

    @property
    @override
    def max_temp(self) -> float:
        """Midea CF Climate max temperature."""
        max_temperature = self._float_attribute(CFAttributes.max_temperature)
        if max_temperature is None:
            return float(TEMPERATURE_MAX)
        return max_temperature

    @property
    @override
    def current_temperature(self) -> float | None:
        """Midea CF Climate current temperature."""
        return self._float_attribute(CFAttributes.current_temperature)


class MideaC3Climate(MideaClimate):
    """Midea C3 Climate Entries."""

    _device: MideaC3Device
    _zone: int

    _powers: tuple[C3Attributes, ...] = (
        C3Attributes.zone1_power,
        C3Attributes.zone2_power,
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]

    def __init__(
        self,
        device: MideaC3Device,
        description: MideaClimateEntityDescription,
        zone: int,
    ) -> None:
        """Midea C3 Climate entity init."""
        super().__init__(device, description)
        self._zone = zone
        self._power_attr = MideaC3Climate._powers[zone]

    def _temperature(self, *, minimum: bool) -> list[float]:
        """Midea C3 Climate temperature."""
        value = (
            C3Attributes.temperature_min if minimum else C3Attributes.temperature_max
        )
        temperatures = self._device.get_attribute(value)
        fallback = float(TEMPERATURE_MIN_C3 if minimum else TEMPERATURE_MAX_C3)
        if not isinstance(temperatures, list):
            return [fallback, fallback]
        parsed_temperatures = [float(temperature) for temperature in temperatures]
        if len(parsed_temperatures) < 2:
            return [fallback, fallback]
        return [
            fallback if temperature == 0.0 else temperature
            for temperature in parsed_temperatures
        ]

    _attr_supported_features = FEATURES_TARGET_AND_POWER

    @property
    @override
    def target_temperature_step(self) -> float:
        """Midea C3 Climate target temperature step."""
        zone_temp_type = self._device.get_attribute(C3Attributes.zone_temp_type)
        if not isinstance(zone_temp_type, list) or len(zone_temp_type) <= self._zone:
            return float(PRECISION_HALVES)
        return float(
            PRECISION_WHOLE if zone_temp_type[self._zone] else PRECISION_HALVES,
        )

    @property
    @override
    def min_temp(self) -> float:
        """Midea C3 Climate min temperature."""
        return self._temperature(minimum=True)[self._zone]

    @property
    @override
    def max_temp(self) -> float:
        """Midea C3 Climate max temperature."""
        return self._temperature(minimum=False)[self._zone]

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Midea C3 Climate turn on."""
        self._device.set_attribute(attr=self._power_attr, value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Midea C3 Climate turn off."""
        self._device.set_attribute(attr=self._power_attr, value=False)

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Midea C3 Climate hvac mode."""
        power = self._device.get_attribute(self._power_attr)
        if not isinstance(power, bool):
            return None
        if not power:
            return HVACMode.OFF
        mode = self._device.get_attribute(C3Attributes.mode)
        if isinstance(mode, int):
            return self._protocol_mode_to_hvac(mode)
        return None

    @property
    @override
    def target_temperature(self) -> float | None:
        """Midea C3 Climate target temperature."""
        target_temperature = self._device.get_attribute(C3Attributes.target_temperature)
        if (
            not isinstance(target_temperature, list)
            or len(target_temperature) <= self._zone
        ):
            return None
        return float(target_temperature[self._zone])

    @property
    @override
    def current_temperature(self) -> float | None:
        """Midea C3 Climate current temperature."""
        return self._float_attribute(C3Attributes.temp_tw_out)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea C3 Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self._device.set_mode(self._zone, self._hvac_to_protocol_mode(hvac_mode))


class MideaFBClimate(MideaClimate):
    """Midea FB Climate Entries."""

    _device: MideaFBDevice

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = PRECISION_WHOLE

    def __init__(
        self,
        device: MideaFBDevice,
        description: MideaClimateEntityDescription,
    ) -> None:
        """Midea FB Climate entity init."""
        super().__init__(device, description)
        self._attr_preset_modes: list[str] = self._device.modes

    @property
    @override
    def preset_mode(self) -> str | None:
        """Midea FB Climate preset mode."""
        preset_mode = self._device.get_attribute(attr=FBAttributes.mode)
        if not isinstance(preset_mode, str):
            return None
        return preset_mode

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Midea FB Climate hvac mode."""
        hvac_mode = self._device.get_attribute(attr=FBAttributes.power)
        if not isinstance(hvac_mode, bool):
            return None
        return HVACMode.HEAT if hvac_mode else HVACMode.OFF

    @property
    @override
    def current_temperature(self) -> float | None:
        """Midea FB Climate current temperature."""
        return self._float_attribute(FBAttributes.current_temperature)

    @override
    def set_temperature(self, **kwargs: Any) -> None:
        """Midea FB Climate set temperature."""
        wants_heat = kwargs.get(ATTR_HVAC_MODE) == HVACMode.HEAT
        if wants_heat and self.hvac_mode == HVACMode.OFF:
            self.turn_on()
        super().set_temperature(**kwargs)

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea FB Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self.turn_on()

    @override
    def set_preset_mode(self, preset_mode: str) -> None:
        """Midea FB Climate set preset mode."""
        self._device.set_attribute(attr=FBAttributes.mode, value=preset_mode)
