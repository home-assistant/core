"""The Homee climate platform."""

from typing import Any

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeNode

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .const import CLIMATE_PROFILES, DOMAIN, HOMEE_UNIT_TO_HA_UNIT, PRESET_MANUAL
from .entity import HomeeNodeEntity

PARALLEL_UPDATES = 0

ROOM_THERMOSTATS = {
    NodeProfile.ROOM_THERMOSTAT,
    NodeProfile.ROOM_THERMOSTAT_WITH_HUMIDITY_SENSOR,
    NodeProfile.WIFI_ROOM_THERMOSTAT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the climate component."""

    async_add_devices(
        HomeeClimate(node, config_entry)
        for node in config_entry.runtime_data.nodes
        if node.profile in CLIMATE_PROFILES
    )


class HomeeClimate(HomeeNodeEntity, ClimateEntity):
    """Representation of a Homee climate entity."""

    _attr_name = None
    _attr_translation_key = DOMAIN

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize a Homee climate entity."""
        super().__init__(node, entry)

        (
            self._attr_supported_features,
            self._attr_hvac_modes,
            self._attr_preset_modes,
        ) = get_climate_features(self._node)

        self._target_temp = self._node.get_attribute_by_type(
            AttributeType.TARGET_TEMPERATURE
        )
        assert self._target_temp is not None
        self._attr_temperature_unit = str(HOMEE_UNIT_TO_HA_UNIT[self._target_temp.unit])
        self._attr_target_temperature_step = self._target_temp.step_value
        self._attr_unique_id = f"{self._attr_unique_id}-{self._target_temp.id}"

        self._heating_mode = self._node.get_attribute_by_type(
            AttributeType.HEATING_MODE
        )
        self._temperature = self._node.get_attribute_by_type(AttributeType.TEMPERATURE)
        self._valve_position = self._node.get_attribute_by_type(
            AttributeType.CURRENT_VALVE_POSITION
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the hvac operation mode."""
        if ClimateEntityFeature.TURN_OFF in self.supported_features and (
            self._heating_mode is not None
        ):
            if self._heating_mode.current_value == 0:
                return HVACMode.OFF

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return the hvac action."""
        if self._heating_mode is not None and self._heating_mode.current_value == 0:
            return HVACAction.OFF

        if (
            self._valve_position is not None and self._valve_position.current_value == 0
        ) or (
            self._temperature is not None
            and self._temperature.current_value >= self.target_temperature
        ):
            return HVACAction.IDLE

        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str:
        """Return the present preset mode."""
        if (
            ClimateEntityFeature.PRESET_MODE in self.supported_features
            and self._heating_mode is not None
            and self._heating_mode.current_value > 0
        ):
            assert self._attr_preset_modes is not None
            return self._attr_preset_modes[int(self._heating_mode.current_value) - 1]

        return PRESET_NONE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._temperature is not None:
            return self._temperature.current_value
        return None

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        assert self._target_temp is not None
        return self._target_temp.current_value

    @property
    def min_temp(self) -> float:
        """Return the lowest settable target temperature."""
        assert self._target_temp is not None
        return self._target_temp.minimum

    @property
    def max_temp(self) -> float:
        """Return the lowest settable target temperature."""
        assert self._target_temp is not None
        return self._target_temp.maximum

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Currently only HEAT and OFF are supported.
        assert self._heating_mode is not None
        await self.async_set_homee_value(
            self._heating_mode, float(hvac_mode == HVACMode.HEAT)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        assert self._heating_mode is not None and self._attr_preset_modes is not None
        await self.async_set_homee_value(
            self._heating_mode, self._attr_preset_modes.index(preset_mode) + 1
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        assert self._target_temp is not None
        if ATTR_TEMPERATURE in kwargs:
            await self.async_set_homee_value(
                self._target_temp, kwargs[ATTR_TEMPERATURE]
            )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        assert self._heating_mode is not None
        await self.async_set_homee_value(self._heating_mode, 1)

    async def async_turn_off(self) -> None:
        """Turn the entity on."""
        assert self._heating_mode is not None
        await self.async_set_homee_value(self._heating_mode, 0)


def get_climate_features(
    node: HomeeNode,
) -> tuple[ClimateEntityFeature, list[HVACMode], list[str] | None]:
    """Determine supported climate features of a node based on the available attributes."""
    features = ClimateEntityFeature.TARGET_TEMPERATURE
    hvac_modes = [HVACMode.HEAT]
    preset_modes: list[str] = []

    if (
        attribute := node.get_attribute_by_type(AttributeType.HEATING_MODE)
    ) is not None:
        features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        hvac_modes.append(HVACMode.OFF)

        if attribute.maximum > 1:
            # Node supports more modes than off and heating.
            features |= ClimateEntityFeature.PRESET_MODE
            preset_modes.extend([PRESET_ECO, PRESET_BOOST, PRESET_MANUAL])

    if len(preset_modes) > 0:
        preset_modes.insert(0, PRESET_NONE)
    return (features, hvac_modes, preset_modes if len(preset_modes) > 0 else None)
