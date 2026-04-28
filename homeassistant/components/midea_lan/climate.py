"""Midea Climate entries."""

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any, cast

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FanSpeed
from .entity import MideaEntity

_LOGGER = logging.getLogger(__name__)


TEMPERATURE_MAX = 30
TEMPERATURE_MIN = 16

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

    model: list[int]
    zone: int | None = None


CLIMATE_ENTITIES: list[MideaClimateEntityDescription] = [
    MideaClimateEntityDescription(
        key="climate",
        model=[DeviceType.AC, DeviceType.CC, DeviceType.CF, DeviceType.FB],
        translation_key="climate_key",
    ),
    MideaClimateEntityDescription(
        key="climate_zone1",
        model=[DeviceType.C3],
        translation_key="climate_zone1",
        zone=0,
    ),
    MideaClimateEntityDescription(
        key="climate_zone2",
        model=[DeviceType.C3],
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

_ATTR_TO_PRESET: dict[str, str] = {
    "comfort_mode": PRESET_COMFORT,
    "eco_mode": PRESET_ECO,
    "boost_mode": PRESET_BOOST,
    "sleep_mode": PRESET_SLEEP,
    "frost_protect": PRESET_AWAY,
}

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
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entries."""
    device = config_entry.runtime_data
    if device is None:
        _LOGGER.warning(
            "Unable to set up climate entities: device not found",
        )
        return
    entities: list[MideaClimate] = []
    for description in CLIMATE_ENTITIES:
        if device.device_type not in description.model:
            continue
        if device.device_type == DeviceType.AC:
            # AC entities need the config entry to honor optional humidity exposure.
            entities.append(MideaACClimate(device, description, config_entry))
        elif device.device_type == DeviceType.CC:
            entities.append(MideaCCClimate(device, description))
        elif device.device_type == DeviceType.CF:
            entities.append(MideaCFClimate(device, description))
        elif device.device_type == DeviceType.C3 and description.zone is not None:
            entities.append(MideaC3Climate(device, description, description.zone))
        elif device.device_type == DeviceType.FB:
            entities.append(MideaFBClimate(device, description))
    async_add_entities(entities)


class MideaClimate(MideaEntity, ClimateEntity):
    """Midea Climate Entries Base Class."""

    _device: MideaClimateDevice

    _attr_has_entity_name = True
    _attr_icon = "mdi:air-conditioner"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_max_temp: float = TEMPERATURE_MAX
    _attr_min_temp: float = TEMPERATURE_MIN
    _attr_target_temperature_high: float | None = TEMPERATURE_MAX
    _attr_target_temperature_low: float | None = TEMPERATURE_MIN
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        device: MideaClimateDevice,
        description: MideaClimateEntityDescription,
    ) -> None:
        """Midea Climate entity init."""
        super().__init__(device, description.key)
        self.entity_description = description
        self._attr_name = None

    @property
    def hvac_mode(self) -> HVACMode:
        """Midea Climate hvac mode."""
        if self._device.get_attribute("power"):
            mode = cast("int", self._device.get_attribute("mode"))
            if 0 <= mode < len(self.hvac_modes):
                return self.hvac_modes[mode]
        return HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        """Midea Climate target temperature."""
        return cast("float", self._device.get_attribute("target_temperature"))

    @property
    def current_temperature(self) -> float | None:
        """Midea Climate current temperature."""
        return cast("float | None", self._device.get_attribute("indoor_temperature"))

    @property
    def preset_mode(self) -> str:
        """Midea Climate preset mode."""
        for attr, preset in _ATTR_TO_PRESET.items():
            if self._device.get_attribute(attr):
                return str(preset)

        return str(PRESET_NONE)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Midea Climate extra state attributes."""
        return cast("dict", self._device.attributes)

    def turn_on(self, **kwargs: Any) -> None:
        """Midea Climate turn on."""
        self._device.set_attribute(attr="power", value=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Midea Climate turn off."""
        self._device.set_attribute(attr="power", value=False)

    def set_temperature(self, **kwargs: Any) -> None:
        """Midea Climate set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = round(kwargs[ATTR_TEMPERATURE] * 2) / 2
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            try:
                mode = self.hvac_modes.index(hvac_mode) if hvac_mode else None
                self._device.set_target_temperature(
                    target_temperature=temperature,
                    mode=mode,
                    zone=None,
                )
            except ValueError:
                _LOGGER.exception("Error setting temperature with: %s", kwargs)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self._device.set_attribute(
                attr="mode",
                value=self.hvac_modes.index(hvac_mode),
            )

    def set_preset_mode(self, preset_mode: str) -> None:
        """Midea Climate set preset mode."""
        old_mode = self.preset_mode
        preset_mode = preset_mode.lower()
        if new_attr := _PRESET_TO_ATTR.get(preset_mode):
            self._device.set_attribute(attr=new_attr, value=True)
        elif old_attr := _PRESET_TO_ATTR.get(old_mode):
            # preset_mode is PRESET_NONE or unknown; clear the current active preset
            self._device.set_attribute(attr=old_attr, value=False)

    def update_state(self, status: Any) -> None:
        """Midea Climate update state."""
        if not self.hass:
            _LOGGER.debug(
                "Climate update_state skipped for %s [%s]: HASS is None",
                self.name,
                type(self),
            )
            return
        self.schedule_update_ha_state()


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

    def __init__(
        self,
        device: MideaACDevice,
        description: MideaClimateEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Midea AC Climate entity init."""
        super().__init__(device, description)
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
        ]
        self._attr_swing_modes: list[str] = [
            SWING_OFF,
            SWING_VERTICAL,
            SWING_HORIZONTAL,
            SWING_BOTH,
        ]
        self._attr_preset_modes = [
            PRESET_NONE,
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_BOOST,
            PRESET_SLEEP,
            PRESET_AWAY,
        ]
        # Indoor humidity is only enabled when explicitly configured by the user
        # because some devices report invalid values (0 or 0xFF) for this sensor.
        self._indoor_humidity_enabled = (
            "sensors" in config_entry.options
            and "indoor_humidity" in config_entry.options["sensors"]
        )

    @property
    def fan_mode(self) -> str:
        """Midea AC Climate fan mode."""
        fan_speed = cast("int", self._device.get_attribute(ACAttributes.fan_speed))
        for threshold, mode in self._fan_thresholds:
            if fan_speed > threshold:
                return str(mode)
        return str(FAN_SILENT)

    @property
    def target_temperature_step(self) -> float:
        """Midea AC Climate target temperature step."""
        return float(
            PRECISION_WHOLE if self._device.temperature_step == 1 else PRECISION_HALVES,
        )

    @property
    def swing_mode(self) -> str:
        """Midea AC Climate swing mode."""
        vertical = bool(self._device.get_attribute(ACAttributes.swing_vertical))
        horizontal = bool(self._device.get_attribute(ACAttributes.swing_horizontal))
        return _SWING_STATE_MAP.get((vertical, horizontal), SWING_OFF)

    @property
    def current_humidity(self) -> float | None:
        """Return the current indoor humidity, or None if unavailable."""
        if not self._indoor_humidity_enabled:
            return None
        raw = self._device.get_attribute("indoor_humidity")
        if isinstance(raw, (int, float)) and raw not in {0, 0xFF}:
            return float(raw)
        return None

    @property
    def outdoor_temperature(self) -> float:
        """Midea AC Climate outdoor temperature."""
        return cast(
            "float",
            self._device.get_attribute(ACAttributes.outdoor_temperature),
        )

    def set_fan_mode(self, fan_mode: str) -> None:
        """Midea AC Climate set fan mode."""
        fan_speed = self._fan_speeds.get(fan_mode)
        if fan_speed:
            self._device.set_attribute(attr=ACAttributes.fan_speed, value=fan_speed)

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
    """Midea CC Climate Entries Base Class."""

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
    def fan_modes(self) -> list[str] | None:
        """Midea CC Climate fan modes."""
        return cast("list", self._device.fan_modes)

    @property
    def fan_mode(self) -> str:
        """Midea CC Climate fan mode."""
        return cast("str", self._device.get_attribute(CCAttributes.fan_speed))

    @property
    def target_temperature_step(self) -> float:
        """Midea CC Climate target temperature step."""
        return cast(
            "float",
            self._device.get_attribute(CCAttributes.temperature_precision),
        )

    @property
    def swing_mode(self) -> str:
        """Midea CC Climate swing mode."""
        return str(
            SWING_ON if self._device.get_attribute(CCAttributes.swing) else SWING_OFF,
        )

    def set_fan_mode(self, fan_mode: str) -> None:
        """Midea CC Climate set fan mode."""
        self._device.set_attribute(attr=CCAttributes.fan_speed, value=fan_mode)

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

    @property
    def min_temp(self) -> float:
        """Midea CF Climate min temperature."""
        return cast("float", self._device.get_attribute(CFAttributes.min_temperature))

    @property
    def max_temp(self) -> float:
        """Midea CF Climate max temperature."""
        return cast("float", self._device.get_attribute(CFAttributes.max_temperature))

    @property
    def target_temperature_low(self) -> float:
        """Midea CF Climate target temperature."""
        return cast("float", self._device.get_attribute(CFAttributes.min_temperature))

    @property
    def target_temperature_high(self) -> float:
        """Midea CF Climate target temperature high."""
        return cast("float", self._device.get_attribute(CFAttributes.max_temperature))

    @property
    def current_temperature(self) -> float:
        """Midea CF Climate current temperature."""
        return cast(
            "float",
            self._device.get_attribute(CFAttributes.current_temperature),
        )


class MideaC3Climate(MideaClimate):
    """Midea C3 Climate Entries."""

    _device: MideaC3Device

    _powers: list[C3Attributes] = [
        C3Attributes.zone1_power,
        C3Attributes.zone2_power,
    ]
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

    def _temperature(self, minimum: bool) -> list[str]:
        """Midea C3 Climate temperature.

        Returns:
        -------
        List of temperatures

        """
        # fmt: off
        value = (C3Attributes.temperature_min
            if minimum
            else C3Attributes.temperature_max)
        # fmt: on
        return cast("list[str]", self._device.get_attribute(value))

    _attr_supported_features = FEATURES_TARGET_AND_POWER

    @property
    def target_temperature_step(self) -> float:
        """Midea C3 Climate target temperature step."""
        zone_temp_type = cast(
            "list[str]",
            self._device.get_attribute(C3Attributes.zone_temp_type),
        )
        return float(
            PRECISION_WHOLE if zone_temp_type[self._zone] else PRECISION_HALVES,
        )

    @property
    def min_temp(self) -> float:
        """Midea C3 Climate min temperature."""
        return cast(
            "float",
            self._temperature(True)[self._zone],
        )

    @property
    def max_temp(self) -> float:
        """Midea C3 Climate max temperature."""
        return cast(
            "float",
            self._temperature(False)[self._zone],
        )

    @property
    def target_temperature_low(self) -> float:
        """Midea C3 Climate target temperature low."""
        return cast(
            "float",
            self._temperature(True)[self._zone],
        )

    @property
    def target_temperature_high(self) -> float:
        """Midea C3 Climate target temperature high."""
        return cast(
            "float",
            self._temperature(False)[self._zone],
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Midea C3 Climate turn on."""
        self._device.set_attribute(attr=self._power_attr, value=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Midea C3 Climate turn off."""
        self._device.set_attribute(attr=self._power_attr, value=False)

    @property
    def hvac_mode(self) -> HVACMode:
        """Midea C3 Climate hvac mode."""
        mode = self._device.get_attribute(C3Attributes.mode)
        if self._device.get_attribute(self._power_attr) and isinstance(mode, int):
            return self.hvac_modes[mode]
        return HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        """Midea C3 Climate target temperature."""
        target_temperature = cast(
            "list[str]",
            self._device.get_attribute(C3Attributes.target_temperature),
        )
        return cast(
            "float",
            target_temperature[self._zone],
        )

    @property
    def current_temperature(self) -> float | None:
        """Midea C3 Climate current temperature."""
        return None

    def set_temperature(self, **kwargs: Any) -> None:
        """Midea C3 Climate set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = round(kwargs[ATTR_TEMPERATURE] * 2) / 2
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            try:
                mode = self.hvac_modes.index(hvac_mode) if hvac_mode else None
                self._device.set_target_temperature(
                    target_temperature=temperature,
                    mode=mode,
                    zone=self._zone,
                )
            except ValueError:
                _LOGGER.exception("Error setting temperature with: %s", kwargs)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea C3 Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self._device.set_mode(self._zone, self.hvac_modes.index(hvac_mode))


class MideaFBClimate(MideaClimate):
    """Midea FB Climate Entries."""

    _device: MideaFBDevice

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_max_temp: float = 35
    _attr_min_temp: float = 5
    _attr_target_temperature_high: float | None = 35
    _attr_target_temperature_low: float | None = 5
    _attr_target_temperature_step: float | None = PRECISION_WHOLE

    def __init__(
        self,
        device: MideaFBDevice,
        description: MideaClimateEntityDescription,
    ) -> None:
        """Midea FB Climate entity init."""
        super().__init__(device, description)
        self._attr_preset_modes: list[str] = self._device.modes

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    @property
    def preset_mode(self) -> str:
        """Midea FB Climate preset mode."""
        return cast("str", self._device.get_attribute(attr=FBAttributes.mode))

    @property
    def hvac_mode(self) -> HVACMode:
        """Midea FB Climate hvac mode."""
        return (
            HVACMode.HEAT
            if self._device.get_attribute(attr=FBAttributes.power)
            else HVACMode.OFF
        )

    @property
    def current_temperature(self) -> float:
        """Midea FB Climate current temperature."""
        return cast(
            "float",
            self._device.get_attribute(FBAttributes.current_temperature),
        )

    def set_temperature(self, **kwargs: Any) -> None:
        """Midea FB Climate set temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return
        temperature = round(kwargs[ATTR_TEMPERATURE] * 2) / 2
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self._device.set_target_temperature(
                target_temperature=temperature,
                mode=None,
            )

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Midea FB Climate set hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            self.turn_on()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Midea FB Climate set preset mode."""
        self._device.set_attribute(attr=FBAttributes.mode, value=preset_mode)
