"""Support for Template climates."""

from enum import IntFlag
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MIN_TEMP,
    FAN_LOW,
    PRESET_COMFORT,
    SWING_OFF,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator, validators as template_validators
from .const import DOMAIN
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

CONF_HVAC_MODE_LIST = "hvac_modes"
CONF_PRESET_MODE_LIST = "preset_modes"
CONF_FAN_MODE_LIST = "fan_modes"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_TEMPERATURE_MIN = "min_temp"
CONF_TEMPERATURE_MAX = "max_temp"
CONF_HUMIDITY_MIN = "min_humidity"
CONF_HUMIDITY_MAX = "max_humidity"
CONF_PRECISION = "precision"
CONF_TEMP_STEP = "temp_step"
CONF_MODE_ACTION = "mode_action"
CONF_MAX_ACTION = "max_action"
CONF_PRESETS_FEATURES = "presets_features"

CONF_CURRENT_TEMPERATURE_TEMPLATE = "current_temperature_template"
CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_TARGET_TEMPERATURE_TEMPLATE = "target_temperature_template"
CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE = "target_temperature_high_template"
CONF_TARGET_TEMPERATURE_LOW_TEMPLATE = "target_temperature_low_template"
CONF_TARGET_HUMIDITY_TEMPLATE = "target_humidity_template"
CONF_HVAC_MODE_TEMPLATE = "hvac_mode_template"
CONF_FAN_MODE_TEMPLATE = "fan_mode_template"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_SWING_MODE_TEMPLATE = "swing_mode_template"
CONF_HVAC_ACTION_TEMPLATE = "hvac_action_template"
CONF_PRESETS_TEMPLATE = "presets_template"

CONF_SET_TEMPERATURE_ACTION = "set_temperature"
CONF_SET_HUMIDITY_ACTION = "set_humidity"
CONF_SET_HVAC_MODE_ACTION = "set_hvac_mode"
CONF_SET_FAN_MODE_ACTION = "set_fan_mode"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"
CONF_SET_SWING_MODE_ACTION = "set_swing_mode"
CONF_SET_PRESETS_ACTION = "set_presets"

DEFAULT_NAME = "Template Climate"
DEFAULT_TEMPERATURE = 21.0
DEFAULT_HUMIDITY = 50
DEFAULT_HVAC_MODE = HVACMode.OFF
DEFAULT_PRESET_MODE = PRESET_COMFORT
DEFAULT_FAN_MODE = FAN_LOW
DEFAULT_SWING_MODE = SWING_OFF
DEFAULT_HVAC_MODE_LIST = [HVACMode.OFF, HVACMode.HEAT]
DEFAULT_PRESET_MODE_LIST: list[str] = []
DEFAULT_FAN_MODE_LIST: list[str] = []
DEFAULT_SWING_MODE_LIST: list[str] = []
DEFAULT_TEMP_STEP = 1.0
DEFAULT_MODE_ACTION = "single"
DEFAULT_MAX_ACTION = 1
DEFAULT_PRESETS_FEATURES = 0

SCRIPT_FIELDS = (
    CONF_SET_TEMPERATURE_ACTION,
    CONF_SET_HUMIDITY_ACTION,
    CONF_SET_HVAC_MODE_ACTION,
    CONF_SET_FAN_MODE_ACTION,
    CONF_SET_PRESET_MODE_ACTION,
    CONF_SET_SWING_MODE_ACTION,
    CONF_SET_PRESETS_ACTION,
)

_EXTRA_OPTIMISTIC_OPTIONS = (
    CONF_CURRENT_TEMPERATURE_TEMPLATE,
    CONF_CURRENT_HUMIDITY_TEMPLATE,
    CONF_TARGET_TEMPERATURE_TEMPLATE,
    CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE,
    CONF_TARGET_TEMPERATURE_LOW_TEMPLATE,
    CONF_TARGET_HUMIDITY_TEMPLATE,
    CONF_FAN_MODE_TEMPLATE,
    CONF_PRESET_MODE_TEMPLATE,
    CONF_SWING_MODE_TEMPLATE,
    CONF_HVAC_ACTION_TEMPLATE,
    CONF_PRESETS_TEMPLATE,
)


class TemplateClimateEntityPresetFeature(IntFlag):
    """Supported preset features for template climates."""

    EDITABLE = 1
    PRESERVED = 2
    HVAC_MODE = 4
    FAN_MODE = 8
    SWING_MODE = 16
    TARGET_TEMPERATURE = 32
    TARGET_TEMPERATURE_RANGE = 64
    TARGET_HUMIDITY = 128


def _hvac_mode_list(value: Any) -> list[HVACMode]:
    """Validate and coerce a configured HVAC mode list."""
    return [HVACMode(item) for item in cv.ensure_list(value)]


CLIMATE_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CURRENT_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_LOW_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESETS_TEMPLATE): cv.template,
        vol.Optional(CONF_SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PRESETS_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(
            CONF_HVAC_MODE_LIST, default=DEFAULT_HVAC_MODE_LIST
        ): _hvac_mode_list,
        vol.Optional(CONF_PRESET_MODE_LIST, default=DEFAULT_PRESET_MODE_LIST): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_FAN_MODE_LIST, default=DEFAULT_FAN_MODE_LIST): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_SWING_MODE_LIST, default=DEFAULT_SWING_MODE_LIST): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_TEMPERATURE_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMPERATURE_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY): vol.Coerce(int),
        vol.Optional(CONF_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY): vol.Coerce(int),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_TEMP_STEP, default=DEFAULT_TEMP_STEP): cv.positive_float,
        vol.Optional(CONF_MODE_ACTION, default=DEFAULT_MODE_ACTION): vol.In(
            ["parallel", "queued", "restart", "single"]
        ),
        vol.Optional(CONF_MAX_ACTION, default=DEFAULT_MAX_ACTION): cv.positive_int,
        vol.Optional(CONF_PRESETS_FEATURES, default=DEFAULT_PRESETS_FEATURES): vol.All(
            vol.Coerce(int), vol.Range(min=0), vol.Range(max=255)
        ),
    }
)

CLIMATE_YAML_SCHEMA = CLIMATE_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(make_template_entity_common_modern_schema(CLIMATE_DOMAIN, DEFAULT_NAME).schema)

CLIMATE_CONFIG_ENTRY_SCHEMA = CLIMATE_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template climates."""
    await async_setup_template_platform(
        hass,
        CLIMATE_DOMAIN,
        config,
        StateClimateEntity,
        TriggerClimateEntity,
        async_add_entities,
        discovery_info,
        script_options=SCRIPT_FIELDS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateClimateEntity,
        CLIMATE_CONFIG_ENTRY_SCHEMA,
        script_options=SCRIPT_FIELDS,
    )


@callback
def async_create_preview_climate(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateClimateEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateClimateEntity,
        CLIMATE_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateClimate(AbstractTemplateEntity, ClimateEntity, RestoreEntity):
    """Representation of a template climate entity."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _state_option = CONF_HVAC_MODE_TEMPLATE
    _extra_optimistic_options = _EXTRA_OPTIMISTIC_OPTIONS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, hass: HomeAssistant, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the template climate."""
        self.hass = hass
        self._config = config

        self._attr_temperature_unit = hass.config.units.temperature_unit
        if CONF_PRECISION in config:
            self._attr_precision = config[CONF_PRECISION]
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]
        self._attr_min_temp = config[CONF_TEMPERATURE_MIN]
        self._attr_max_temp = config[CONF_TEMPERATURE_MAX]
        self._attr_min_humidity = config[CONF_HUMIDITY_MIN]
        self._attr_max_humidity = config[CONF_HUMIDITY_MAX]
        self._attr_supported_features = ClimateEntityFeature(0)

        self._attr_hvac_modes = list(config[CONF_HVAC_MODE_LIST])
        self._attr_preset_modes = list(config[CONF_PRESET_MODE_LIST])
        self._attr_fan_modes = list(config[CONF_FAN_MODE_LIST])
        self._attr_swing_modes = list(config[CONF_SWING_MODE_LIST])

        self._attr_current_temperature: float | None = None
        self._attr_current_humidity: int | None = None
        self._attr_hvac_action: HVACAction | None = None
        self._attr_hvac_mode = (
            DEFAULT_HVAC_MODE
            if DEFAULT_HVAC_MODE in self._attr_hvac_modes
            else self._attr_hvac_modes[0]
        )
        self._attr_preset_mode = (
            DEFAULT_PRESET_MODE
            if DEFAULT_PRESET_MODE in self._attr_preset_modes
            else self._attr_preset_modes[0]
            if self._attr_preset_modes
            else None
        )
        self._attr_fan_mode = (
            DEFAULT_FAN_MODE
            if DEFAULT_FAN_MODE in self._attr_fan_modes
            else self._attr_fan_modes[0]
            if self._attr_fan_modes
            else None
        )
        self._attr_swing_mode = (
            DEFAULT_SWING_MODE
            if DEFAULT_SWING_MODE in self._attr_swing_modes
            else self._attr_swing_modes[0]
            if self._attr_swing_modes
            else None
        )
        self._attr_target_temperature = DEFAULT_TEMPERATURE
        self._attr_target_temperature_low = DEFAULT_TEMPERATURE
        self._attr_target_temperature_high = DEFAULT_TEMPERATURE
        self._attr_target_humidity = DEFAULT_HUMIDITY

        self._presets_features = TemplateClimateEntityPresetFeature(
            config[CONF_PRESETS_FEATURES]
        )
        self._presets: dict[str, dict[str, Any]] = {}
        self._off_mode: dict[str, Any] = {}
        self._last_on_mode: dict[str, Any] = {}

        self._configure_supported_features()

        self.setup_state_template(
            "_attr_hvac_mode",
            self._validate_hvac_mode,
            self._update_hvac_mode_state,
        )
        self.setup_template(
            CONF_PRESET_MODE_TEMPLATE,
            "_attr_preset_mode",
            self._validate_preset_mode,
        )
        self.setup_template(
            CONF_FAN_MODE_TEMPLATE,
            "_attr_fan_mode",
            self._validate_fan_mode,
        )
        self.setup_template(
            CONF_SWING_MODE_TEMPLATE,
            "_attr_swing_mode",
            self._validate_swing_mode,
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE_TEMPLATE,
            "_attr_target_temperature",
            self._validate_target_temperature,
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE_LOW_TEMPLATE,
            "_attr_target_temperature_low",
            self._validate_target_temperature_low,
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE,
            "_attr_target_temperature_high",
            self._validate_target_temperature_high,
        )
        self.setup_template(
            CONF_TARGET_HUMIDITY_TEMPLATE,
            "_attr_target_humidity",
            self._validate_target_humidity,
        )
        self.setup_template(
            CONF_CURRENT_TEMPERATURE_TEMPLATE,
            "_attr_current_temperature",
            self._validate_current_temperature,
        )
        self.setup_template(
            CONF_CURRENT_HUMIDITY_TEMPLATE,
            "_attr_current_humidity",
            self._validate_current_humidity,
        )
        self.setup_template(
            CONF_HVAC_ACTION_TEMPLATE,
            "_attr_hvac_action",
            self._validate_hvac_action,
        )
        self.setup_template(
            CONF_PRESETS_TEMPLATE,
            "_presets",
            self._validate_presets,
            render_complex=True,
        )

        for script_id in SCRIPT_FIELDS:
            if (action_config := config.get(script_id)) is not None:
                self._action_scripts[script_id] = Script(
                    hass,
                    action_config,
                    f"{name} {script_id}",
                    DOMAIN,
                    script_mode=config[CONF_MODE_ACTION],
                    max_runs=config[CONF_MAX_ACTION],
                )

    def _configure_supported_features(self) -> None:
        """Compute supported features from the configured templates and actions."""
        if len(self._attr_hvac_modes) >= 2 and HVACMode.OFF in self._attr_hvac_modes:
            self._off_mode["hvac_mode"] = HVACMode.OFF
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
            self._last_on_mode["hvac_mode"] = next(
                (
                    mode
                    for mode in self._attr_hvac_modes
                    if mode != self._off_mode["hvac_mode"]
                ),
                self._attr_hvac_modes[0],
            )

        if self._attr_preset_modes:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        if self._attr_fan_modes:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        if self._attr_swing_modes:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
        if HVACMode.HEAT_COOL in self._attr_hvac_modes:
            self._attr_supported_features |= (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            )
        if any(
            mode in self._attr_hvac_modes
            for mode in (HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL)
        ):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if (
            CONF_SET_HUMIDITY_ACTION in self._config
            or CONF_TARGET_HUMIDITY_TEMPLATE in self._config
            or self._presets_features
            & TemplateClimateEntityPresetFeature.TARGET_HUMIDITY
        ):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

    def _validate_choice(
        self, attribute: str, result: Any, valid: list[str]
    ) -> str | None:
        """Validate a string value against configured choices."""
        if template_validators.check_result_for_none(
            result, none_on_unknown_unavailable=True
        ):
            return None

        value = str(result)
        if value not in valid:
            template_validators.log_validation_result_error(
                self, attribute, result, tuple(valid)
            )
            return None
        return value

    def _validate_hvac_mode(self, result: Any) -> HVACMode | None:
        """Validate the HVAC mode template result."""
        if template_validators.check_result_for_none(
            result, none_on_unknown_unavailable=True
        ):
            return None

        try:
            value = HVACMode(str(result).lower().strip())
        except ValueError:
            template_validators.log_validation_result_error(
                self,
                CONF_HVAC_MODE_TEMPLATE,
                result,
                tuple(mode.value for mode in self._attr_hvac_modes),
            )
            return None

        if value not in self._attr_hvac_modes:
            template_validators.log_validation_result_error(
                self,
                CONF_HVAC_MODE_TEMPLATE,
                result,
                tuple(mode.value for mode in self._attr_hvac_modes),
            )
            return None
        return value

    def _validate_preset_mode(self, result: Any) -> str | None:
        return self._validate_choice(
            CONF_PRESET_MODE_TEMPLATE, result, self._attr_preset_modes or []
        )

    def _validate_fan_mode(self, result: Any) -> str | None:
        return self._validate_choice(
            CONF_FAN_MODE_TEMPLATE, result, self._attr_fan_modes or []
        )

    def _validate_swing_mode(self, result: Any) -> str | None:
        return self._validate_choice(
            CONF_SWING_MODE_TEMPLATE, result, self._attr_swing_modes or []
        )

    def _validate_hvac_action(self, result: Any) -> HVACAction | None:
        """Validate the HVAC action template result."""
        if template_validators.check_result_for_none(
            result, none_on_unknown_unavailable=True
        ):
            return None

        try:
            return HVACAction(str(result).lower().strip())
        except ValueError:
            template_validators.log_validation_result_error(
                self,
                CONF_HVAC_ACTION_TEMPLATE,
                result,
                tuple(action.value for action in HVACAction),
            )
            return None

    def _restore_mode_state(self, result: Any) -> dict[str, Any]:
        """Normalize restored mode state attributes."""
        if not isinstance(result, dict):
            return {}

        restored = dict(result)
        if "hvac_mode" not in restored:
            return restored

        if (hvac_mode := self._validate_hvac_mode(restored["hvac_mode"])) is None:
            restored.pop("hvac_mode")
        else:
            restored["hvac_mode"] = hvac_mode

        return restored

    def _validate_current_temperature(self, result: Any) -> float | None:
        """Validate a current temperature template result."""
        if (
            value := template_validators.number(
                self, CONF_CURRENT_TEMPERATURE_TEMPLATE
            )(result)
        ) is None:
            return None

        if self.precision == PRECISION_HALVES:
            return round(float(value) / 0.5) * 0.5
        if self.precision == PRECISION_TENTHS:
            return round(float(value), 1)
        return round(float(value))

    def _validate_target_temperature(
        self,
        result: Any,
        attribute: str = CONF_TARGET_TEMPERATURE_TEMPLATE,
    ) -> float | None:
        """Validate a target temperature template result."""
        if (
            value := template_validators.number(
                self,
                attribute,
                self._attr_min_temp,
                self._attr_max_temp,
            )(result)
        ) is None:
            return None

        if self._attr_target_temperature_step is None:
            return float(value)

        return (
            round(float(value) / self._attr_target_temperature_step)
            * self._attr_target_temperature_step
        )

    def _validate_target_temperature_low(self, result: Any) -> float | None:
        """Validate a low target temperature template result."""
        return self._validate_target_temperature(
            result, CONF_TARGET_TEMPERATURE_LOW_TEMPLATE
        )

    def _validate_target_temperature_high(self, result: Any) -> float | None:
        """Validate a high target temperature template result."""
        return self._validate_target_temperature(
            result, CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE
        )

    def _validate_current_humidity(self, result: Any) -> int | None:
        """Validate a current humidity template result."""
        validated = template_validators.number(
            self,
            CONF_CURRENT_HUMIDITY_TEMPLATE,
            0,
            100,
            int,
        )(result)
        return None if validated is None else int(validated)

    def _validate_target_humidity(self, result: Any) -> int | None:
        """Validate a target humidity template result."""
        validated = template_validators.number(
            self,
            CONF_TARGET_HUMIDITY_TEMPLATE,
            self._attr_min_humidity,
            self._attr_max_humidity,
            int,
        )(result)
        return None if validated is None else int(validated)

    def _empty_preset(self) -> dict[str, Any]:
        """Return the default structure for a preset."""
        preset: dict[str, Any] = {}
        if self._presets_features & TemplateClimateEntityPresetFeature.HVAC_MODE:
            preset["hvac_mode"] = None
        if self._presets_features & TemplateClimateEntityPresetFeature.FAN_MODE:
            preset["fan_mode"] = None
        if self._presets_features & TemplateClimateEntityPresetFeature.SWING_MODE:
            preset["swing_mode"] = None
        if (
            self._presets_features
            & TemplateClimateEntityPresetFeature.TARGET_TEMPERATURE
        ):
            preset["target_temperature"] = None
        if (
            self._presets_features
            & TemplateClimateEntityPresetFeature.TARGET_TEMPERATURE_RANGE
        ):
            preset["target_temperature_low"] = None
            preset["target_temperature_high"] = None
        if self._presets_features & TemplateClimateEntityPresetFeature.TARGET_HUMIDITY:
            preset["target_humidity"] = None
        return preset

    def _validate_presets(self, result: Any) -> dict[str, dict[str, Any]]:
        """Validate the presets template result."""
        if template_validators.check_result_for_none(
            result, none_on_unknown_unavailable=True
        ):
            return {}

        if not isinstance(result, dict):
            template_validators.log_validation_result_error(
                self, CONF_PRESETS_TEMPLATE, result, "expected a dictionary"
            )
            return {}

        validated: dict[str, dict[str, Any]] = {}
        for mode in self._attr_preset_modes or []:
            raw_preset = result.get(mode)
            preset = self._empty_preset()
            if not isinstance(raw_preset, dict):
                validated[mode] = preset
                continue

            if (
                self._presets_features & TemplateClimateEntityPresetFeature.HVAC_MODE
                and (value := raw_preset.get("hvac_mode")) is not None
            ):
                preset["hvac_mode"] = self._validate_hvac_mode(value)
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.FAN_MODE
                and (value := raw_preset.get("fan_mode")) is not None
            ):
                preset["fan_mode"] = self._validate_choice(
                    "fan_mode", value, self._attr_fan_modes or []
                )
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.SWING_MODE
                and (value := raw_preset.get("swing_mode")) is not None
            ):
                preset["swing_mode"] = self._validate_choice(
                    "swing_mode", value, self._attr_swing_modes or []
                )
            if (
                self._presets_features
                & TemplateClimateEntityPresetFeature.TARGET_TEMPERATURE
                and (value := raw_preset.get("target_temperature")) is not None
            ):
                preset["target_temperature"] = self._validate_target_temperature(value)
            if (
                self._presets_features
                & TemplateClimateEntityPresetFeature.TARGET_TEMPERATURE_RANGE
            ):
                if (value := raw_preset.get("target_temperature_low")) is not None:
                    preset["target_temperature_low"] = (
                        self._validate_target_temperature_low(value)
                    )
                if (value := raw_preset.get("target_temperature_high")) is not None:
                    preset["target_temperature_high"] = (
                        self._validate_target_temperature_high(value)
                    )
            if (
                self._presets_features
                & TemplateClimateEntityPresetFeature.TARGET_HUMIDITY
                and (value := raw_preset.get("target_humidity")) is not None
            ):
                preset["target_humidity"] = self._validate_target_humidity(value)
            validated[mode] = preset

        return validated

    @callback
    def _update_hvac_mode_state(self, hvac_mode: HVACMode | None) -> None:
        """Update the HVAC mode and tracked last-on mode."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode is not None and self._off_mode.get("hvac_mode") != hvac_mode:
            self._last_on_mode["hvac_mode"] = hvac_mode

    async def _async_restore_state(self) -> None:
        """Restore state for optimistic climates."""
        if (last_state := await self.async_get_last_state()) is None:
            return

        if CONF_HVAC_MODE_TEMPLATE not in self._templates:
            self._update_hvac_mode_state(self._validate_hvac_mode(last_state.state))

        if (
            CONF_PRESET_MODE_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_PRESET_MODE)) is not None
        ):
            self._attr_preset_mode = self._validate_preset_mode(value)

        if (
            CONF_FAN_MODE_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_FAN_MODE)) is not None
        ):
            self._attr_fan_mode = self._validate_fan_mode(value)

        if (
            CONF_SWING_MODE_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_SWING_MODE)) is not None
        ):
            self._attr_swing_mode = self._validate_swing_mode(value)

        if (
            CONF_TARGET_TEMPERATURE_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_TEMPERATURE)) is not None
            and (validated := self._validate_target_temperature(value)) is not None
        ):
            self._attr_target_temperature = validated

        if (
            CONF_TARGET_TEMPERATURE_LOW_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_TARGET_TEMP_LOW)) is not None
            and (validated := self._validate_target_temperature_low(value)) is not None
        ):
            self._attr_target_temperature_low = validated

        if (
            CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_TARGET_TEMP_HIGH)) is not None
            and (validated := self._validate_target_temperature_high(value)) is not None
        ):
            self._attr_target_temperature_high = validated

        if (
            CONF_TARGET_HUMIDITY_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_HUMIDITY)) is not None
            and (validated := self._validate_target_humidity(value)) is not None
        ):
            self._attr_target_humidity = validated

        if (
            CONF_CURRENT_TEMPERATURE_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_CURRENT_TEMPERATURE))
            is not None
            and (validated := self._validate_current_temperature(value)) is not None
        ):
            self._attr_current_temperature = validated

        if (
            CONF_CURRENT_HUMIDITY_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_CURRENT_HUMIDITY)) is not None
            and (validated := self._validate_current_humidity(value)) is not None
        ):
            self._attr_current_humidity = validated

        if (
            CONF_HVAC_ACTION_TEMPLATE not in self._templates
            and (value := last_state.attributes.get(ATTR_HVAC_ACTION)) is not None
        ):
            self._attr_hvac_action = self._validate_hvac_action(value)

        if (value := last_state.attributes.get("last_on_mode")) is not None:
            self._last_on_mode.update(self._restore_mode_state(value))
        if (value := last_state.attributes.get("off_mode")) is not None:
            self._off_mode.update(self._restore_mode_state(value))
        if (
            CONF_PRESETS_TEMPLATE not in self._templates
            and (value := last_state.attributes.get("presets")) is not None
        ):
            self._presets = self._validate_presets(value)

    def _write_state_for(self, template_options: set[str]) -> bool:
        """Return if local state should be written after an action."""
        return self._attr_assumed_state or any(
            option not in self._templates for option in template_options
        )

    async def _async_run_action(
        self, script_id: str, variables: dict[str, Any]
    ) -> None:
        """Run a configured action script."""
        if not variables or (script := self._action_scripts.get(script_id)) is None:
            return

        trigger_context_id = None if self._context is None else self._context.id
        script_context = Context(parent_id=trigger_context_id)
        await self.async_run_script(
            script,
            run_variables=variables,
            context=script_context,
        )

    async def _async_run_presets_action(
        self, changed_presets: dict[str, dict[str, Any]]
    ) -> None:
        """Persist editable preset changes via the optional presets action."""
        if not changed_presets:
            return

        await self._async_run_action(
            CONF_SET_PRESETS_ACTION,
            {"presets": self._presets, "changed": changed_presets},
        )

    async def async_turn_off(self) -> None:
        """Turn the climate off."""
        if (off_mode := self._off_mode.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(off_mode)

    async def async_turn_on(self) -> None:
        """Turn the climate on."""
        if (last_on_mode := self._last_on_mode.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(last_on_mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if hvac_mode not in self._attr_hvac_modes:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")

        self._update_hvac_mode_state(hvac_mode)
        if self._write_state_for({CONF_HVAC_MODE_TEMPLATE}):
            self.async_write_ha_state()
        await self._async_run_action(
            CONF_SET_HVAC_MODE_ACTION,
            {ATTR_HVAC_MODE: hvac_mode},
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if preset_mode not in (self._attr_preset_modes or []):
            raise ValueError(f"Unsupported preset mode: {preset_mode}")

        self._attr_preset_mode = preset_mode
        if self._write_state_for({CONF_PRESET_MODE_TEMPLATE}):
            self.async_write_ha_state()
        await self._async_run_action(
            CONF_SET_PRESET_MODE_ACTION,
            {ATTR_PRESET_MODE: preset_mode},
        )

        if preset_mode in self._presets:
            await self.async_set_presets(self._presets[preset_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if fan_mode not in (self._attr_fan_modes or []):
            raise ValueError(f"Unsupported fan mode: {fan_mode}")

        self._attr_fan_mode = fan_mode
        if self._write_state_for({CONF_FAN_MODE_TEMPLATE}):
            self.async_write_ha_state()
        await self._async_run_action(
            CONF_SET_FAN_MODE_ACTION,
            {ATTR_FAN_MODE: fan_mode},
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        if swing_mode not in (self._attr_swing_modes or []):
            raise ValueError(f"Unsupported swing mode: {swing_mode}")

        self._attr_swing_mode = swing_mode
        if self._write_state_for({CONF_SWING_MODE_TEMPLATE}):
            self.async_write_ha_state()
        await self._async_run_action(
            CONF_SET_SWING_MODE_ACTION,
            {ATTR_SWING_MODE: swing_mode},
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        validated = self._validate_target_humidity(humidity)
        if validated is None:
            raise ValueError(f"Invalid humidity: {humidity}")

        changed_presets: dict[str, dict[str, Any]] = {}
        self._attr_target_humidity = validated
        if (
            self._presets_features & TemplateClimateEntityPresetFeature.EDITABLE
            and self._attr_preset_mode in self._presets
            and "target_humidity" in self._presets[self._attr_preset_mode]
        ):
            self._presets[self._attr_preset_mode]["target_humidity"] = validated
            changed_presets[self._attr_preset_mode] = {"target_humidity": validated}

        if self._write_state_for({CONF_TARGET_HUMIDITY_TEMPLATE}):
            self.async_write_ha_state()
        await self._async_run_action(
            CONF_SET_HUMIDITY_ACTION,
            {ATTR_HUMIDITY: validated},
        )
        await self._async_run_presets_action(changed_presets)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set one or more target temperatures."""
        run_variables: dict[str, Any] = {}
        changed_presets: dict[str, dict[str, Any]] = {}
        template_options: set[str] = set()

        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            if hvac_mode not in self._attr_hvac_modes:
                raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")
            self._update_hvac_mode_state(hvac_mode)
            run_variables[ATTR_HVAC_MODE] = hvac_mode
            template_options.add(CONF_HVAC_MODE_TEMPLATE)
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.EDITABLE
                and self._attr_preset_mode in self._presets
                and "hvac_mode" in self._presets[self._attr_preset_mode]
            ):
                changed_presets.setdefault(self._attr_preset_mode, {})["hvac_mode"] = (
                    hvac_mode
                )
                self._presets[self._attr_preset_mode]["hvac_mode"] = hvac_mode

        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            validated = self._validate_target_temperature(target_temperature)
            if validated is None:
                raise ValueError(f"Invalid target temperature: {target_temperature}")
            self._attr_target_temperature = validated
            run_variables[ATTR_TEMPERATURE] = validated
            template_options.add(CONF_TARGET_TEMPERATURE_TEMPLATE)
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.EDITABLE
                and self._attr_preset_mode in self._presets
                and "target_temperature" in self._presets[self._attr_preset_mode]
            ):
                changed_presets.setdefault(self._attr_preset_mode, {})[
                    "target_temperature"
                ] = validated
                self._presets[self._attr_preset_mode]["target_temperature"] = validated

        if (target_temperature_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            validated = self._validate_target_temperature_low(target_temperature_low)
            if validated is None:
                raise ValueError(
                    f"Invalid low target temperature: {target_temperature_low}"
                )
            self._attr_target_temperature_low = validated
            run_variables[ATTR_TARGET_TEMP_LOW] = validated
            template_options.add(CONF_TARGET_TEMPERATURE_LOW_TEMPLATE)
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.EDITABLE
                and self._attr_preset_mode in self._presets
                and "target_temperature_low" in self._presets[self._attr_preset_mode]
            ):
                changed_presets.setdefault(self._attr_preset_mode, {})[
                    "target_temperature_low"
                ] = validated
                self._presets[self._attr_preset_mode]["target_temperature_low"] = (
                    validated
                )

        if (target_temperature_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            validated = self._validate_target_temperature_high(target_temperature_high)
            if validated is None:
                raise ValueError(
                    f"Invalid high target temperature: {target_temperature_high}"
                )
            self._attr_target_temperature_high = validated
            run_variables[ATTR_TARGET_TEMP_HIGH] = validated
            template_options.add(CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE)
            if (
                self._presets_features & TemplateClimateEntityPresetFeature.EDITABLE
                and self._attr_preset_mode in self._presets
                and "target_temperature_high" in self._presets[self._attr_preset_mode]
            ):
                changed_presets.setdefault(self._attr_preset_mode, {})[
                    "target_temperature_high"
                ] = validated
                self._presets[self._attr_preset_mode]["target_temperature_high"] = (
                    validated
                )

        if not run_variables:
            return

        if self._write_state_for(template_options):
            self.async_write_ha_state()
        await self._async_run_action(CONF_SET_TEMPERATURE_ACTION, run_variables)
        await self._async_run_presets_action(changed_presets)

    async def async_set_presets(self, preset: dict[str, Any]) -> None:
        """Apply values stored in a preset definition."""
        temperature_data: dict[str, Any] = {}
        if (value := preset.get("target_temperature")) is not None:
            temperature_data[ATTR_TEMPERATURE] = value
        if (value := preset.get("target_temperature_low")) is not None:
            temperature_data[ATTR_TARGET_TEMP_LOW] = value
        if (value := preset.get("target_temperature_high")) is not None:
            temperature_data[ATTR_TARGET_TEMP_HIGH] = value
        hvac_mode = preset.get("hvac_mode")
        if temperature_data:
            if hvac_mode is not None:
                temperature_data[ATTR_HVAC_MODE] = hvac_mode
            await self.async_set_temperature(**temperature_data)
        elif hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

        if (value := preset.get("fan_mode")) is not None:
            await self.async_set_fan_mode(value)
        if (value := preset.get("swing_mode")) is not None:
            await self.async_set_swing_mode(value)
        if (value := preset.get("target_humidity")) is not None:
            await self.async_set_humidity(value)

    @property
    def target_temperature(self) -> float | None:
        """Return the active single target temperature."""
        if self._attr_hvac_mode == HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature

    @property
    def target_temperature_low(self) -> float | None:
        """Return the low target temperature for range mode."""
        if self._attr_hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the high target temperature for range mode."""
        if self._attr_hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature_high

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return climate-specific extra attributes."""
        return {
            "presets": self._presets,
            "last_on_mode": self._last_on_mode,
            "off_mode": self._off_mode,
        }


class StateClimateEntity(TemplateEntity, AbstractTemplateClimate):
    """Representation of a state-based template climate."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the state-based template climate."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateClimate.__init__(self, hass, name, config)

    async def async_added_to_hass(self) -> None:
        """Restore state after entity has been added."""
        await super().async_added_to_hass()
        await self._async_restore_state()


class TriggerClimateEntity(TriggerEntity, AbstractTemplateClimate):
    """Representation of a trigger-based template climate."""

    domain = CLIMATE_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the trigger-based template climate."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateClimate.__init__(self, hass, name, config)

    async def async_added_to_hass(self) -> None:
        """Restore state after entity has been added."""
        await super().async_added_to_hass()
        await self._async_restore_state()
