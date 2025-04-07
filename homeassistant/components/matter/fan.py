"""Matter Fan platform support."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

FanControlFeature = clusters.FanControl.Bitmaps.Feature
WindBitmap = clusters.FanControl.Bitmaps.WindBitmap
FanModeSequenceEnum = clusters.FanControl.Enums.FanModeSequenceEnum

PRESET_LOW = "low"
PRESET_MEDIUM = "medium"
PRESET_HIGH = "high"
PRESET_AUTO = "auto"
FAN_MODE_MAP = {
    PRESET_LOW: clusters.FanControl.Enums.FanModeEnum.kLow,
    PRESET_MEDIUM: clusters.FanControl.Enums.FanModeEnum.kMedium,
    PRESET_HIGH: clusters.FanControl.Enums.FanModeEnum.kHigh,
    PRESET_AUTO: clusters.FanControl.Enums.FanModeEnum.kAuto,
}
FAN_MODE_MAP_REVERSE = {v: k for k, v in FAN_MODE_MAP.items()}
# special preset modes for wind feature
PRESET_NATURAL_WIND = "natural_wind"
PRESET_SLEEP_WIND = "sleep_wind"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter fan from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.FAN, async_add_entities)


class MatterFan(MatterEntity, FanEntity):
    """Representation of a Matter fan."""

    _last_known_preset_mode: str | None = None
    _last_known_percentage: int = 0

    _feature_map: int | None = None
    _platform_translation_key = "fan"

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None and preset_mode is None:
            # turn_on without explicit percentage or preset_mode given
            # try to handle this with the last known value
            if self._last_known_percentage != 0:
                percentage = self._last_known_percentage
            elif self._last_known_preset_mode is not None:
                preset_mode = self._last_known_preset_mode
            elif self._attr_preset_modes:
                # fallback: default to first supported preset
                preset_mode = self._attr_preset_modes[0]
            else:
                # this really should not be possible but handle it anyways
                percentage = 50

        # prefer setting fan speed by percentage
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        # handle setting fan mode by preset
        if TYPE_CHECKING:
            assert preset_mode is not None
        await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn fan off."""
        # clear the wind setting if its currently set
        if self._attr_preset_mode in [PRESET_NATURAL_WIND, PRESET_SLEEP_WIND]:
            await self._set_wind_mode(None)
        await self.write_attribute(
            value=clusters.FanControl.Enums.FanModeEnum.kOff,
            matter_attribute=clusters.FanControl.Attributes.FanMode,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        await self.write_attribute(
            value=percentage,
            matter_attribute=clusters.FanControl.Attributes.PercentSetting,
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # handle wind as preset
        if preset_mode in [PRESET_NATURAL_WIND, PRESET_SLEEP_WIND]:
            await self._set_wind_mode(preset_mode)
            return

        # clear the wind setting if its currently set
        if self._attr_preset_mode in [PRESET_NATURAL_WIND, PRESET_SLEEP_WIND]:
            await self._set_wind_mode(None)

        await self.write_attribute(
            value=FAN_MODE_MAP[preset_mode],
            matter_attribute=clusters.FanControl.Attributes.FanMode,
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self.write_attribute(
            value=(
                self.get_matter_attribute_value(
                    clusters.FanControl.Attributes.RockSupport
                )
                if oscillating
                else 0
            ),
            matter_attribute=clusters.FanControl.Attributes.RockSetting,
        )

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.write_attribute(
            value=(
                clusters.FanControl.Enums.AirflowDirectionEnum.kReverse
                if direction == DIRECTION_REVERSE
                else clusters.FanControl.Enums.AirflowDirectionEnum.kForward
            ),
            matter_attribute=clusters.FanControl.Attributes.AirflowDirection,
        )

    async def _set_wind_mode(self, wind_mode: str | None) -> None:
        """Set wind mode."""
        if wind_mode == PRESET_NATURAL_WIND:
            wind_setting = WindBitmap.kNaturalWind
        elif wind_mode == PRESET_SLEEP_WIND:
            wind_setting = WindBitmap.kSleepWind
        else:
            wind_setting = 0
        await self.write_attribute(
            value=wind_setting,
            matter_attribute=clusters.FanControl.Attributes.WindSetting,
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()

        if self.get_matter_attribute_value(clusters.OnOff.Attributes.OnOff) is False:
            # special case: the appliance has a dedicated Power switch on the OnOff cluster
            # if the mains power is off - treat it as if the fan mode is off
            self._attr_preset_mode = None
            self._attr_percentage = 0
            return

        if self._attr_supported_features & FanEntityFeature.DIRECTION:
            direction_value = self.get_matter_attribute_value(
                clusters.FanControl.Attributes.AirflowDirection
            )
            self._attr_current_direction = (
                DIRECTION_REVERSE
                if direction_value
                == clusters.FanControl.Enums.AirflowDirectionEnum.kReverse
                else DIRECTION_FORWARD
            )
        if self._attr_supported_features & FanEntityFeature.OSCILLATE:
            self._attr_oscillating = (
                self.get_matter_attribute_value(
                    clusters.FanControl.Attributes.RockSetting
                )
                != 0
            )

        # speed percentage is always provided
        current_percent = self.get_matter_attribute_value(
            clusters.FanControl.Attributes.PercentCurrent
        )
        # NOTE that a device may give back 255 as a special value to indicate that
        # the speed is under automatic control and not set to a specific value.
        self._attr_percentage = None if current_percent == 255 else current_percent

        # get preset mode from fan mode (and wind feature if available)
        wind_setting = self.get_matter_attribute_value(
            clusters.FanControl.Attributes.WindSetting
        )
        fan_mode = self.get_matter_attribute_value(
            clusters.FanControl.Attributes.FanMode
        )
        if fan_mode == clusters.FanControl.Enums.FanModeEnum.kOff:
            self._attr_preset_mode = None
            self._attr_percentage = 0
        elif (
            self._attr_preset_modes
            and PRESET_NATURAL_WIND in self._attr_preset_modes
            and wind_setting & WindBitmap.kNaturalWind
        ):
            self._attr_preset_mode = PRESET_NATURAL_WIND
        elif (
            self._attr_preset_modes
            and PRESET_SLEEP_WIND in self._attr_preset_modes
            and wind_setting & WindBitmap.kSleepWind
        ):
            self._attr_preset_mode = PRESET_SLEEP_WIND
        else:
            fan_mode = self.get_matter_attribute_value(
                clusters.FanControl.Attributes.FanMode
            )
            self._attr_preset_mode = FAN_MODE_MAP_REVERSE.get(fan_mode)

        # keep track of the last known mode for turn_on commands without preset
        if self._attr_preset_mode is not None:
            self._last_known_preset_mode = self._attr_preset_mode
        if current_percent:
            self._last_known_percentage = current_percent

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA Fan platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(clusters.FanControl.Attributes.FeatureMap)
        )
        # NOTE: the featuremap can dynamically change, so we need to update the
        # supported features if the featuremap changes.
        # work out supported features and presets from matter featuremap
        if self._feature_map == feature_map:
            return
        self._feature_map = feature_map
        self._attr_supported_features = FanEntityFeature(0)
        if feature_map & FanControlFeature.kMultiSpeed:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._attr_speed_count = int(
                self.get_matter_attribute_value(clusters.FanControl.Attributes.SpeedMax)
            )
        if feature_map & FanControlFeature.kRocking:
            # NOTE: the Matter model allows that a device can have multiple/different
            # rock directions while HA doesn't allow this in the entity model.
            # For now we just assume that a device has a single rock direction and the
            # Matter spec is just future proofing for devices that might have multiple
            # rock directions. As soon as devices show up that actually support multiple
            # directions, we need to either update the HA Fan entity model or maybe add
            # this as a separate entity.
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

        # figure out supported preset modes
        preset_modes = []
        fan_mode_seq = int(
            self.get_matter_attribute_value(
                clusters.FanControl.Attributes.FanModeSequence
            )
        )
        if fan_mode_seq == FanModeSequenceEnum.kOffLowHigh:
            preset_modes = [PRESET_LOW, PRESET_HIGH]
        elif fan_mode_seq == FanModeSequenceEnum.kOffLowHighAuto:
            preset_modes = [PRESET_LOW, PRESET_HIGH, PRESET_AUTO]
        elif fan_mode_seq == FanModeSequenceEnum.kOffLowMedHigh:
            preset_modes = [PRESET_LOW, PRESET_MEDIUM, PRESET_HIGH]
        elif fan_mode_seq == FanModeSequenceEnum.kOffLowMedHighAuto:
            preset_modes = [PRESET_LOW, PRESET_MEDIUM, PRESET_HIGH, PRESET_AUTO]
        elif fan_mode_seq == FanModeSequenceEnum.kOffHighAuto:
            preset_modes = [PRESET_HIGH, PRESET_AUTO]
        elif fan_mode_seq == FanModeSequenceEnum.kOffHigh:
            preset_modes = [PRESET_HIGH]
        # treat Matter Wind feature as additional preset(s)
        if feature_map & FanControlFeature.kWind:
            wind_support = int(
                self.get_matter_attribute_value(
                    clusters.FanControl.Attributes.WindSupport
                )
            )
            if wind_support & WindBitmap.kNaturalWind:
                preset_modes.append(PRESET_NATURAL_WIND)
            if wind_support & WindBitmap.kSleepWind:
                preset_modes.append(PRESET_SLEEP_WIND)
        if len(preset_modes) > 0:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
        self._attr_preset_modes = preset_modes
        if feature_map & FanControlFeature.kAirflowDirection:
            self._attr_supported_features |= FanEntityFeature.DIRECTION

        self._attr_supported_features |= (
            FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.FAN,
        entity_description=FanEntityDescription(
            key="MatterFan",
            name=None,
        ),
        entity_class=MatterFan,
        # FanEntityFeature
        required_attributes=(
            clusters.FanControl.Attributes.FanMode,
            clusters.FanControl.Attributes.PercentCurrent,
        ),
        optional_attributes=(
            clusters.FanControl.Attributes.SpeedSetting,
            clusters.FanControl.Attributes.RockSetting,
            clusters.FanControl.Attributes.WindSetting,
            clusters.FanControl.Attributes.AirflowDirection,
            clusters.OnOff.Attributes.OnOff,
        ),
    ),
]
