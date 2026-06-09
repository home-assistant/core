"""Platform for climate integration."""

from typing import Any

from whirlpool.aircon import Aircon, FanSpeed as AirconFanSpeed, Mode as AirconMode
from whirlpool.oven import Cavity as OvenCavity, CavityState, CookMode, Oven

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SWING_HORIZONTAL,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolEntity, WhirlpoolOvenEntity

PARALLEL_UPDATES = 1

AIRCON_MODE_MAP = {
    AirconMode.Cool: HVACMode.COOL,
    AirconMode.Heat: HVACMode.HEAT,
    AirconMode.Fan: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_AIRCON_MODE = {v: k for k, v in AIRCON_MODE_MAP.items()}

AIRCON_FANSPEED_MAP = {
    AirconFanSpeed.Off: FAN_OFF,
    AirconFanSpeed.Auto: FAN_AUTO,
    AirconFanSpeed.Low: FAN_LOW,
    AirconFanSpeed.Medium: FAN_MEDIUM,
    AirconFanSpeed.High: FAN_HIGH,
}

FAN_MODE_TO_AIRCON_FANSPEED = {v: k for k, v in AIRCON_FANSPEED_MAP.items()}

SUPPORTED_MAX_TEMP = 30
SUPPORTED_MIN_TEMP = 16
SUPPORTED_SWING_MODES = [SWING_HORIZONTAL, SWING_OFF]
SUPPORTED_TARGET_TEMPERATURE_STEP = 1

# Oven cook modes exposed as climate preset modes. The string values match the
# oven cook-mode sensor so translations are shared.
OVEN_COOK_MODE_MAP = {
    CookMode.Bake: "bake",
    CookMode.ConvectBake: "convection_bake",
    CookMode.Broil: "broil",
    CookMode.ConvectBroil: "convection_broil",
    CookMode.ConvectRoast: "convection_roast",
    CookMode.KeepWarm: "keep_warm",
    CookMode.AirFry: "air_fry",
}
PRESET_MODE_TO_COOK_MODE = {v: k for k, v in OVEN_COOK_MODE_MAP.items()}
OVEN_PRESET_MODES = list(OVEN_COOK_MODE_MAP.values())

# Oven temperatures are in Celsius.
SUPPORTED_OVEN_MIN_TEMP = 30
SUPPORTED_OVEN_MAX_TEMP = 290
SUPPORTED_OVEN_TARGET_TEMPERATURE_STEP = 5
# Used when a cook is started from idle without a target temperature set yet.
DEFAULT_OVEN_TEMP = 175

OVEN_ACTIVE_STATES = (CavityState.Preheating, CavityState.Cooking)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    appliances_manager = config_entry.runtime_data

    entities: list[ClimateEntity] = [
        AirConEntity(aircon) for aircon in appliances_manager.aircons
    ]
    entities.extend(
        OvenEntity(oven, cavity)
        for oven in appliances_manager.ovens
        for cavity in (OvenCavity.Upper, OvenCavity.Lower)
        if oven.get_oven_cavity_exists(cavity)
    )
    async_add_entities(entities)


class AirConEntity(WhirlpoolEntity, ClimateEntity):
    """Representation of an air conditioner."""

    _appliance: Aircon

    _attr_name = None
    _attr_fan_modes = [*FAN_MODE_TO_AIRCON_FANSPEED.keys()]
    _attr_hvac_modes = [HVACMode.OFF, *HVAC_MODE_TO_AIRCON_MODE.keys()]
    _attr_max_temp = SUPPORTED_MAX_TEMP
    _attr_min_temp = SUPPORTED_MIN_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_swing_modes = SUPPORTED_SWING_MODES
    _attr_target_temperature_step = SUPPORTED_TARGET_TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._appliance.get_current_temp()

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._appliance.get_temp()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        AirConEntity._check_service_request(
            await self._appliance.set_temp(kwargs.get(ATTR_TEMPERATURE))
        )

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._appliance.get_current_humidity()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, fan."""
        if not self._appliance.get_power_on():
            return HVACMode.OFF

        mode: AirconMode = self._appliance.get_mode()
        return AIRCON_MODE_MAP.get(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            AirConEntity._check_service_request(
                await self._appliance.set_power_on(False)
            )
            return

        mode = HVAC_MODE_TO_AIRCON_MODE[hvac_mode]
        AirConEntity._check_service_request(await self._appliance.set_mode(mode))
        if not self._appliance.get_power_on():
            AirConEntity._check_service_request(
                await self._appliance.set_power_on(True)
            )

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        fanspeed = self._appliance.get_fanspeed()
        return AIRCON_FANSPEED_MAP.get(fanspeed, FAN_OFF)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        fanspeed = FAN_MODE_TO_AIRCON_FANSPEED[fan_mode]
        AirConEntity._check_service_request(
            await self._appliance.set_fanspeed(fanspeed)
        )

    @property
    def swing_mode(self) -> str:
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._appliance.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        AirConEntity._check_service_request(
            await self._appliance.set_h_louver_swing(swing_mode == SWING_HORIZONTAL)
        )

    async def async_turn_on(self) -> None:
        """Turn device on."""
        AirConEntity._check_service_request(await self._appliance.set_power_on(True))

    async def async_turn_off(self) -> None:
        """Turn device off."""
        AirConEntity._check_service_request(await self._appliance.set_power_on(False))


class OvenEntity(WhirlpoolOvenEntity, ClimateEntity):
    """Representation of an oven cavity's cooking control."""

    _appliance: Oven

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = OVEN_PRESET_MODES
    _attr_max_temp = SUPPORTED_OVEN_MAX_TEMP
    _attr_min_temp = SUPPORTED_OVEN_MIN_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = SUPPORTED_OVEN_TARGET_TEMPERATURE_STEP
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, appliance: Oven, cavity: OvenCavity) -> None:
        """Initialize the oven climate entity."""
        super().__init__(appliance, cavity, translation_key_base="oven")
        # For a single-cavity oven this entity represents the whole device, so
        # use the device name; dual-cavity ovens keep the per-cavity name.
        if not (
            appliance.get_oven_cavity_exists(OvenCavity.Upper)
            and appliance.get_oven_cavity_exists(OvenCavity.Lower)
        ):
            self._attr_name = None

    @property
    def current_temperature(self) -> float | None:
        """Return the current cavity temperature."""
        return self._appliance.get_temp(self.cavity)

    @property
    def target_temperature(self) -> float | None:
        """Return the target cavity temperature."""
        return self._appliance.get_target_temp(self.cavity)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HEAT while preheating/cooking, otherwise OFF."""
        if self._appliance.get_cavity_state(self.cavity) in OVEN_ACTIVE_STATES:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current action."""
        if self._appliance.get_cavity_state(self.cavity) in OVEN_ACTIVE_STATES:
            return HVACAction.HEATING
        return HVACAction.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return the current cook mode, if it is a selectable one."""
        return OVEN_COOK_MODE_MAP.get(self._appliance.get_cook_mode(self.cavity))

    def _active_cook_mode(self) -> CookMode:
        """Return the current cook mode, defaulting to Bake when idle."""
        mode = self._appliance.get_cook_mode(self.cavity)
        if mode is None or mode == CookMode.Standby:
            return CookMode.Bake
        return mode

    def _active_target_temp(self) -> float:
        """Return the current target temp, defaulting when none is set."""
        return self._appliance.get_target_temp(self.cavity) or DEFAULT_OVEN_TEMP

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature (keeps the current cook mode)."""
        OvenEntity._check_service_request(
            await self._appliance.set_cook(
                target_temp=kwargs[ATTR_TEMPERATURE],
                mode=self._active_cook_mode(),
                cavity=self.cavity,
            )
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the cook mode (keeps the current/last target temperature)."""
        OvenEntity._check_service_request(
            await self._appliance.set_cook(
                target_temp=self._active_target_temp(),
                mode=PRESET_MODE_TO_COOK_MODE[preset_mode],
                cavity=self.cavity,
            )
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop cooking."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Start cooking with the current/default mode and target."""
        OvenEntity._check_service_request(
            await self._appliance.set_cook(
                target_temp=self._active_target_temp(),
                mode=self._active_cook_mode(),
                cavity=self.cavity,
            )
        )

    async def async_turn_off(self) -> None:
        """Stop cooking."""
        OvenEntity._check_service_request(
            await self._appliance.stop_cook(self.cavity)
        )
