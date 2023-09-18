"""Support for a ScreenLogic heating device."""
from dataclasses import dataclass
import logging
from typing import Any

from screenlogicpy.const.common import UNIT
from screenlogicpy.const.data import ATTR, DEVICE, VALUE
from screenlogicpy.const.msg import CODE
from screenlogicpy.device_const.heat import HEAT_MODE
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN as SL_DOMAIN
from .coordinator import ScreenlogicDataUpdateCoordinator
from .entity import ScreenLogicPushEntity, ScreenLogicPushEntityDescription

_LOGGER = logging.getLogger(__name__)


SUPPORTED_MODES = [HVACMode.OFF, HVACMode.HEAT]

SUPPORTED_PRESETS = [
    HEAT_MODE.SOLAR,
    HEAT_MODE.SOLAR_PREFERRED,
    HEAT_MODE.HEATER,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""
    entities = []
    coordinator: ScreenlogicDataUpdateCoordinator = hass.data[SL_DOMAIN][
        config_entry.entry_id
    ]

    gateway = coordinator.gateway

    for body_index, body_data in gateway.get_data(DEVICE.BODY).items():
        body_path = (DEVICE.BODY, body_index)
        entities.append(
            ScreenLogicClimate(
                coordinator,
                ScreenLogicClimateDescription(
                    subscription_code=CODE.STATUS_CHANGED,
                    data_path=body_path,
                    key=body_index,
                    name=body_data[VALUE.HEAT_STATE][ATTR.NAME],
                ),
            )
        )

    async_add_entities(entities)


@dataclass
class ScreenLogicClimateDescription(
    ClimateEntityDescription, ScreenLogicPushEntityDescription
):
    """Describes a ScreenLogic climate entity."""


class ScreenLogicClimate(ScreenLogicPushEntity, ClimateEntity, RestoreEntity):
    """Represents a ScreenLogic climate entity."""

    entity_description: ScreenLogicClimateDescription
    _attr_hvac_modes = SUPPORTED_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator, entity_description) -> None:
        """Initialize a ScreenLogic climate entity."""
        super().__init__(coordinator, entity_description)
        self._configured_heat_modes = []
        # Is solar listed as available equipment?
        if EQUIPMENT_FLAG.SOLAR in self.gateway.equipment_flags:
            self._configured_heat_modes.extend(
                [HEAT_MODE.SOLAR, HEAT_MODE.SOLAR_PREFERRED]
            )
        self._configured_heat_modes.append(HEAT_MODE.HEATER)

        self._attr_min_temp = self.entity_data[ATTR.MIN_SETPOINT]
        self._attr_max_temp = self.entity_data[ATTR.MAX_SETPOINT]
        self._last_preset = None

    @property
    def current_temperature(self) -> float:
        """Return water temperature."""
        return self.entity_data[VALUE.LAST_TEMPERATURE][ATTR.VALUE]

    @property
    def target_temperature(self) -> float:
        """Target temperature."""
        return self.entity_data[VALUE.HEAT_SETPOINT][ATTR.VALUE]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.gateway.temperature_unit == UNIT.CELSIUS:
            return UnitOfTemperature.CELSIUS
        return UnitOfTemperature.FAHRENHEIT

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current hvac mode."""
        if self.entity_data[VALUE.HEAT_MODE][ATTR.VALUE] > 0:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current action of the heater."""
        if self.entity_data[VALUE.HEAT_STATE][ATTR.VALUE] > 0:
            return HVACAction.HEATING
        if self.hvac_mode == HVACMode.HEAT:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def preset_mode(self) -> str:
        """Return current/last preset mode."""
        if self.hvac_mode == HVACMode.OFF:
            return HEAT_MODE(self._last_preset).title
        return HEAT_MODE(self.entity_data[VALUE.HEAT_MODE][ATTR.VALUE]).title

    @property
    def preset_modes(self) -> list[str]:
        """All available presets."""
        return [HEAT_MODE(mode_num).title for mode_num in self._configured_heat_modes]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Change the setpoint of the heater."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise ValueError(f"Expected attribute {ATTR_TEMPERATURE}")

        if not await self.gateway.async_set_heat_temp(
            int(self._data_key), int(temperature)
        ):
            raise HomeAssistantError(
                f"Failed to set_temperature {temperature} on body"
                f" {self.entity_data[ATTR.BODY_TYPE][ATTR.VALUE]}"
            )
        _LOGGER.debug("Set temperature for body %s to %s", self._data_key, temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the operation mode."""
        if hvac_mode == HVACMode.OFF:
            mode = HEAT_MODE.OFF
        else:
            mode = HEAT_MODE.parse(self.preset_mode)

        if not await self.gateway.async_set_heat_mode(
            int(self._data_key), int(mode.value)
        ):
            raise HomeAssistantError(
                f"Failed to set_hvac_mode {mode.name} on body"
                f" {self.entity_data[ATTR.BODY_TYPE][ATTR.VALUE]}"
            )
        _LOGGER.debug("Set hvac_mode on body %s to %s", self._data_key, mode.name)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        mode = HEAT_MODE.parse(preset_mode)
        _LOGGER.debug("Setting last_preset to %s", mode.name)
        self._last_preset = mode.value
        if self.hvac_mode == HVACMode.OFF:
            return

        if not await self.gateway.async_set_heat_mode(
            int(self._data_key), int(mode.value)
        ):
            raise HomeAssistantError(
                f"Failed to set_preset_mode {mode.name} on body"
                f" {self.entity_data[ATTR.BODY_TYPE][ATTR.VALUE]}"
            )
        _LOGGER.debug("Set preset_mode on body %s to %s", self._data_key, mode.name)

    async def async_added_to_hass(self) -> None:
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
            mode = HEAT_MODE.parse(prev_state.attributes.get(ATTR_PRESET_MODE))
            _LOGGER.debug(
                "Startup setting last_preset to %s from prev_state",
                mode.name,
            )
            self._last_preset = mode.value
        else:
            mode = HEAT_MODE.parse(self._configured_heat_modes[0])
            _LOGGER.debug(
                "Startup setting last_preset to default (%s)",
                mode.name,
            )
            self._last_preset = mode.value
