"""Midea Climate entries."""

from collections.abc import Mapping
import logging
from typing import Any, ClassVar, cast

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
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICE_ID,
    CONF_SWITCHES,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICES, DOMAIN, FanSpeed
from .devices import MIDEA_DEVICES
from .entity import MideaEntity

_LOGGER = logging.getLogger(__name__)


TEMPERATURE_MAX = 30
TEMPERATURE_MIN = 16

FAN_SILENT = "silent"
FAN_FULL_SPEED = "full"

type MideaClimateDevice = (
    MideaACDevice | MideaCCDevice | MideaCFDevice | MideaC3Device | MideaFBDevice
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entries."""
    device_id = config_entry.data.get(CONF_DEVICE_ID)
    device = hass.data[DOMAIN][DEVICES].get(device_id)
    extra_switches = config_entry.options.get(CONF_SWITCHES, [])
    devs: list[
        MideaACClimate
        | MideaCCClimate
        | MideaCFClimate
        | MideaC3Climate
        | MideaFBClimate
    ] = []
    for entity_key, config in cast(
        "dict",
        MIDEA_DEVICES[device.device_type]["entities"],
    ).items():
        if config["type"] == Platform.CLIMATE and (
            config.get("default") or entity_key in extra_switches
        ):
            if device.device_type == DeviceType.AC:
                # add config_entry args to fix indoor_humidity error bug
                devs.append(MideaACClimate(device, entity_key, config_entry))
            elif device.device_type == DeviceType.CC:
                devs.append(MideaCCClimate(device, entity_key))
            elif device.device_type == DeviceType.CF:
                devs.append(MideaCFClimate(device, entity_key))
            elif device.device_type == DeviceType.C3:
                devs.append(MideaC3Climate(device, entity_key, config["zone"]))
            elif device.device_type == DeviceType.FB:
                devs.append(MideaFBClimate(device, entity_key))
    async_add_entities(devs)


class MideaClimate(MideaEntity, ClimateEntity):
    """Midea Climate Entries Base Class."""

    # https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded
    _enable_turn_on_off_backwards_compatibility: bool = (
        False  # maybe remove after 2025.1
    )

    _device: MideaClimateDevice

    _attr_max_temp: float = TEMPERATURE_MAX
    _attr_min_temp: float = TEMPERATURE_MIN
    _attr_target_temperature_high: float | None = TEMPERATURE_MAX
    _attr_target_temperature_low: float | None = TEMPERATURE_MIN
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS

    def __init__(self, device: MideaClimateDevice, entity_key: str) -> None:
        """Midea Climate entity init."""
        super().__init__(device, entity_key)

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Midea Climate supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Midea Climate hvac mode."""
        if self._device.get_attribute("power"):
            mode = cast("int", self._device.get_attribute("mode"))
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
        if self._device.get_attribute("comfort_mode"):
            mode = PRESET_COMFORT
        elif self._device.get_attribute("eco_mode"):
            mode = PRESET_ECO
        elif self._device.get_attribute("boost_mode"):
            mode = PRESET_BOOST
        elif self._device.get_attribute("sleep_mode"):
            mode = PRESET_SLEEP
        elif self._device.get_attribute("frost_protect"):
            mode = PRESET_AWAY
        else:
            mode = PRESET_NONE
        return str(mode)

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
        temperature = float(int((float(kwargs[ATTR_TEMPERATURE]) * 2) + 0.5)) / 2
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            try:
                mode = self.hvac_modes.index(hvac_mode.lower()) if hvac_mode else None
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
        if preset_mode == PRESET_AWAY:
            self._device.set_attribute(attr="frost_protect", value=True)
        elif preset_mode == PRESET_COMFORT:
            self._device.set_attribute(attr="comfort_mode", value=True)
        elif preset_mode == PRESET_SLEEP:
            self._device.set_attribute(attr="sleep_mode", value=True)
        elif preset_mode == PRESET_ECO:
            self._device.set_attribute(attr="eco_mode", value=True)
        elif preset_mode == PRESET_BOOST:
            self._device.set_attribute(attr="boost_mode", value=True)
        elif old_mode == PRESET_AWAY:
            self._device.set_attribute(attr="frost_protect", value=False)
        elif old_mode == PRESET_COMFORT:
            self._device.set_attribute(attr="comfort_mode", value=False)
        elif old_mode == PRESET_SLEEP:
            self._device.set_attribute(attr="sleep_mode", value=False)
        elif old_mode == PRESET_ECO:
            self._device.set_attribute(attr="eco_mode", value=False)
        elif old_mode == PRESET_BOOST:
            self._device.set_attribute(attr="boost_mode", value=False)

    def update_state(self, status: Any) -> None:
        """Midea Climate update state."""
        if not self.hass:
            _LOGGER.warning(
                "Climate update_state skipped for %s [%s]: HASS is None",
                self.name,
                type(self),
            )
            return
        self.schedule_update_ha_state()


class MideaACClimate(MideaClimate):
    """Midea AC Climate Entries."""

    _device: MideaACDevice

    def __init__(
        self,
        device: MideaACDevice,
        entity_key: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Midea AC Climate entity init."""
        super().__init__(device, entity_key)
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
        ]
        self._fan_speeds: dict[str, int] = {
            FAN_SILENT: 20,
            FAN_LOW: 40,
            FAN_MEDIUM: 60,
            FAN_HIGH: 80,
            FAN_FULL_SPEED: 100,
            FAN_AUTO: 102,
        }
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
        self._attr_fan_modes = list(self._fan_speeds.keys())
        # fix error humidity value, disable indoor_humidity
        # add config_entry args to fix indoor_humidity error bug
        self._indoor_humidity_enabled = (
            "sensors" in config_entry.options
            and "indoor_humidity" in config_entry.options["sensors"]
        )

    @property
    def fan_mode(self) -> str:
        """Midea AC Climate fan mode."""
        fan_speed = cast("int", self._device.get_attribute(ACAttributes.fan_speed))
        if fan_speed > FanSpeed.AUTO:
            return str(FAN_AUTO)
        if fan_speed > FanSpeed.FULL_SPEED:
            return str(FAN_FULL_SPEED)
        if fan_speed > FanSpeed.HIGH:
            return str(FAN_HIGH)
        if fan_speed > FanSpeed.MEDIUM:
            return str(FAN_MEDIUM)
        if fan_speed > FanSpeed.LOW:
            return str(FAN_LOW)
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
        swing_mode = (
            1 if self._device.get_attribute(ACAttributes.swing_vertical) else 0
        ) + (2 if self._device.get_attribute(ACAttributes.swing_horizontal) else 0)
        return self._attr_swing_modes[swing_mode]

    @property
    def current_humidity(self) -> float | None:
        """Return the current indoor humidity, or None if unavailable."""
        # fix error humidity, disable indoor_humidity in web UI
        # https://github.com/wuwentao/midea_ac_lan/pull/641
        if not self._indoor_humidity_enabled:
            return None
        raw = self._device.get_attribute("indoor_humidity")
        if isinstance(raw, (int, float)) and raw not in {0, 0xFF}:
            return float(raw)
        # indoor_humidity is 0 or 255, return None
        # https://github.com/wuwentao/midea_ac_lan/pull/614
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
        swing = self._attr_swing_modes.index(swing_mode)
        swing_vertical = swing & 1 > 0
        swing_horizontal = swing & 2 > 0
        self._device.set_swing(
            swing_vertical=swing_vertical,
            swing_horizontal=swing_horizontal,
        )


class MideaCCClimate(MideaClimate):
    """Midea CC Climate Entries Base Class."""

    _device: MideaCCDevice

    def __init__(self, device: MideaCCDevice, entity_key: str) -> None:
        """Midea CC Climate entity init."""
        super().__init__(device, entity_key)
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
        ]
        self._attr_swing_modes = [SWING_OFF, SWING_ON]
        self._attr_preset_modes = [PRESET_NONE, PRESET_SLEEP, PRESET_ECO]

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

    _attr_target_temperature_step: float | None = PRECISION_WHOLE

    def __init__(self, device: MideaCFDevice, entity_key: str) -> None:
        """Midea CF Climate entity init."""
        super().__init__(device, entity_key)
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
        ]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Midea CF Climate supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

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

    _powers: ClassVar[list[C3Attributes]] = [
        C3Attributes.zone1_power,
        C3Attributes.zone2_power,
    ]

    def __init__(self, device: MideaC3Device, entity_key: str, zone: int) -> None:
        """Midea C3 Climate entity init."""
        super().__init__(device, entity_key)
        self._zone = zone
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
        ]
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

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Midea C3 Climate supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

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
        temperature = float(int((float(kwargs[ATTR_TEMPERATURE]) * 2) + 0.5)) / 2
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
        else:
            try:
                mode = self.hvac_modes.index(hvac_mode.lower()) if hvac_mode else None
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

    _attr_max_temp: float = 35
    _attr_min_temp: float = 5
    _attr_target_temperature_high: float | None = 35
    _attr_target_temperature_low: float | None = 5
    _attr_target_temperature_step: float | None = PRECISION_WHOLE

    def __init__(self, device: MideaFBDevice, entity_key: str) -> None:
        """Midea FB Climate entity init."""
        super().__init__(device, entity_key)
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._attr_preset_modes: list[str] = self._device.modes

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Midea FB Climate supported features."""
        return (
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
        temperature = float(int((float(kwargs[ATTR_TEMPERATURE]) * 2) + 0.5)) / 2
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
