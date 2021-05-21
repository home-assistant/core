"""Support for a ScreenLogic heating device."""
import logging

from screenlogicpy.const import DATA as SL_DATA, EQUIPMENT, HEAT_MODE

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

SUPPORTED_MODES = [HVAC_MODE_OFF, HVAC_MODE_HEAT]

SUPPORTED_PRESETS = [
    HEAT_MODE.SOLAR,
    HEAT_MODE.SOLAR_PREFERRED,
    HEAT_MODE.HEATER,
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    for body in coordinator.data[SL_DATA.KEY_BODIES]:
        entities.append(ScreenLogicClimate(coordinator, body))

    async_add_entities(entities)


class ScreenLogicClimate(ScreenlogicEntity, ClimateEntity, RestoreEntity):
    """Represents a ScreenLogic climate entity."""

    def __init__(self, coordinator, body):
        """Initialize a ScreenLogic climate entity."""
        super().__init__(coordinator, body)
        self._configured_heat_modes = []
        # Is solar listed as available equipment?
        if self.coordinator.data["config"]["equipment_flags"] & EQUIPMENT.FLAG_SOLAR:
            self._configured_heat_modes.extend(
                [HEAT_MODE.SOLAR, HEAT_MODE.SOLAR_PREFERRED]
            )
        self._configured_heat_modes.append(HEAT_MODE.HEATER)
        self._last_preset = None

    @property
    def name(self) -> str:
        """Name of the heater."""
        ent_name = self.body["heat_status"]["name"]
        return f"{self.gateway_name} {ent_name}"

    @property
    def min_temp(self) -> float:
        """Minimum allowed temperature."""
        return self.body["min_set_point"]["value"]

    @property
    def max_temp(self) -> float:
        """Maximum allowed temperature."""
        return self.body["max_set_point"]["value"]

    @property
    def current_temperature(self) -> float:
        """Return water temperature."""
        return self.body["last_temperature"]["value"]

    @property
    def target_temperature(self) -> float:
        """Target temperature."""
        return self.body["heat_set_point"]["value"]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.config_data["is_celsius"]["value"] == 1:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def hvac_mode(self) -> str:
        """Return the current hvac mode."""
        if self.body["heat_mode"]["value"] > 0:
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return th supported hvac modes."""
        return SUPPORTED_MODES

    @property
    def hvac_action(self) -> str:
        """Return the current action of the heater."""
        if self.body["heat_status"]["value"] > 0:
            return CURRENT_HVAC_HEAT
        if self.hvac_mode == HVAC_MODE_HEAT:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_OFF

    @property
    def preset_mode(self) -> str:
        """Return current/last preset mode."""
        if self.hvac_mode == HVAC_MODE_OFF:
            return HEAT_MODE.NAME_FOR_NUM[self._last_preset]
        return HEAT_MODE.NAME_FOR_NUM[self.body["heat_mode"]["value"]]

    @property
    def preset_modes(self):
        """All available presets."""
        return [
            HEAT_MODE.NAME_FOR_NUM[mode_num] for mode_num in self._configured_heat_modes
        ]

    @property
    def supported_features(self):
        """Supported features of the heater."""
        return SUPPORTED_FEATURES

    async def async_set_temperature(self, **kwargs) -> None:
        """Change the setpoint of the heater."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError(f"Expected attribute {ATTR_TEMPERATURE}")

        async with self.coordinator.api_lock:
            success = await self.hass.async_add_executor_job(
                self.gateway.set_heat_temp, int(self._data_key), int(temperature)
            )

        if success:
            await self.coordinator.async_request_refresh()
        else:
            raise HomeAssistantError(
                f"Failed to set_temperature {temperature} on body {self.body['body_type']['value']}"
            )

    async def async_set_hvac_mode(self, hvac_mode) -> None:
        """Set the operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            mode = HEAT_MODE.OFF
        else:
            mode = HEAT_MODE.NUM_FOR_NAME[self.preset_mode]

        async with self.coordinator.api_lock:
            success = await self.hass.async_add_executor_job(
                self.gateway.set_heat_mode, int(self._data_key), int(mode)
            )

        if success:
            await self.coordinator.async_request_refresh()
        else:
            raise HomeAssistantError(
                f"Failed to set_hvac_mode {mode} on body {self.body['body_type']['value']}"
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        _LOGGER.debug("Setting last_preset to %s", HEAT_MODE.NUM_FOR_NAME[preset_mode])
        self._last_preset = mode = HEAT_MODE.NUM_FOR_NAME[preset_mode]
        if self.hvac_mode == HVAC_MODE_OFF:
            return

        async with self.coordinator.api_lock:
            success = await self.hass.async_add_executor_job(
                self.gateway.set_heat_mode, int(self._data_key), int(mode)
            )

        if success:
            await self.coordinator.async_request_refresh()
        else:
            raise HomeAssistantError(
                f"Failed to set_preset_mode {mode} on body {self.body['body_type']['value']}"
            )

    async def async_added_to_hass(self):
        """Run when entity is about to be added."""
        await super().async_added_to_hass()

        _LOGGER.debug("Startup last preset is %s", self._last_preset)
        if self._last_preset is not None:
            return
        prev_state = await self.async_get_last_state()
        if (
            prev_state is not None
            and prev_state.attributes.get(ATTR_PRESET_MODE) is not None
        ):
            _LOGGER.debug(
                "Startup setting last_preset to %s from prev_state",
                HEAT_MODE.NUM_FOR_NAME[prev_state.attributes.get(ATTR_PRESET_MODE)],
            )
            self._last_preset = HEAT_MODE.NUM_FOR_NAME[
                prev_state.attributes.get(ATTR_PRESET_MODE)
            ]
        else:
            _LOGGER.debug(
                "Startup setting last_preset to default (%s)",
                self._configured_heat_modes[0],
            )
            self._last_preset = self._configured_heat_modes[0]

    @property
    def body(self):
        """Shortcut to access body data."""
        return self.coordinator.data[SL_DATA.KEY_BODIES][self._data_key]
