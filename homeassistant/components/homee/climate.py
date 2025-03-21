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
    """Add the Homee platform for the climate integration."""

    async_add_devices(
        HomeeClimate(node, config_entry)
        for node in config_entry.runtime_data.nodes
        if node.profile in CLIMATE_PROFILES
    )


class HomeeClimate(HomeeNodeEntity, ClimateEntity):
    """Representation of a Homee climate device."""

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

        self._traget_temp = self._node.get_attribute_by_type(
            AttributeType.TARGET_TEMPERATURE
        )
        assert self._traget_temp is not None
        self._attr_temperature_unit = str(HOMEE_UNIT_TO_HA_UNIT[self._traget_temp.unit])
        self._attr_target_temperature_step = self._traget_temp.step_value
        self._attr_unique_id = f"{self._attr_unique_id}-{self._traget_temp.id}"

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the hvac operation mode."""
        if ClimateEntityFeature.TURN_OFF in self.supported_features and (
            (attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE))
            is not None
        ):
            if attribute.current_value == 0:
                return HVACMode.OFF

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return the hvac action."""
        if ClimateEntityFeature.TURN_OFF in self.supported_features and (
            (attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE))
            is not None
        ):
            if attribute.current_value == 0:
                return HVACAction.OFF

        if (
            attribute := self._node.get_attribute_by_type(
                AttributeType.CURRENT_VALVE_POSITION
            )
        ) is not None:
            if attribute.current_value == 0:
                return HVACAction.IDLE

        if (
            self.current_temperature
            and self.current_temperature >= self.target_temperature
        ):
            return HVACAction.IDLE

        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str:
        """Return the present preset mode."""
        if (
            ClimateEntityFeature.PRESET_MODE in self.supported_features
            and (
                attribute := self._node.get_attribute_by_type(
                    AttributeType.HEATING_MODE
                )
            )
            is not None
        ):
            assert self._attr_preset_modes is not None
            return self._attr_preset_modes[int(attribute.current_value) - 1]

        return PRESET_NONE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (
            temp := self._node.get_attribute_by_type(AttributeType.TEMPERATURE)
        ) is not None:
            return temp.current_value
        return None

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        assert self._traget_temp is not None
        return self._traget_temp.current_value

    @property
    def min_temp(self) -> float:
        """Return the lowest settable target temperature."""
        assert self._traget_temp is not None
        return self._traget_temp.minimum

    @property
    def max_temp(self) -> float:
        """Return the lowest settable target temperature."""
        assert self._traget_temp is not None
        return self._traget_temp.maximum

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        # Currently only HEAT and OFF are supported.
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE)
        ) is not None:
            await self.async_set_homee_value(
                attribute, float(hvac_mode == HVACMode.HEAT)
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE)
        ) is not None:
            assert self._attr_preset_modes is not None
            await self.async_set_homee_value(
                attribute, self._attr_preset_modes.index(preset_mode) + 1
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""

        assert self._traget_temp is not None
        if ATTR_TEMPERATURE in kwargs:
            await self.async_set_homee_value(
                self._traget_temp, kwargs[ATTR_TEMPERATURE]
            )

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE)
        ) is not None:
            await self.async_set_homee_value(attribute, 1)

    async def async_turn_off(self) -> None:
        """Turn the entity on."""
        if (
            attribute := self._node.get_attribute_by_type(AttributeType.HEATING_MODE)
        ) is not None:
            await self.async_set_homee_value(attribute, 0)


def get_climate_features(
    node: HomeeNode,
) -> tuple[ClimateEntityFeature, list[HVACMode], list[str] | None]:
    """Determine supported climate features of a node based on the available attributes."""
    features = ClimateEntityFeature.TARGET_TEMPERATURE
    hvac_modes = [HVACMode.HEAT]
    preset_modes: list[str] = []

    if node.get_attribute_by_type(AttributeType.HEATING_MODE) is not None:
        features |= ClimateEntityFeature.TURN_ON
        features |= ClimateEntityFeature.TURN_OFF
        hvac_modes.append(HVACMode.OFF)

        if (
            attribute := node.get_attribute_by_type(AttributeType.HEATING_MODE)
        ) is not None and attribute.maximum > 1:
            # Node supports more modes than off and heating.
            features |= ClimateEntityFeature.PRESET_MODE
            preset_modes.extend([PRESET_ECO, PRESET_BOOST, PRESET_MANUAL])

    if len(preset_modes) > 0:
        preset_modes.insert(0, PRESET_NONE)
    return (features, hvac_modes, preset_modes if len(preset_modes) > 0 else None)
