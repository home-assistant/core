"""Support for Template climates."""

from collections.abc import Callable
import contextlib
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    ENTITY_ID_FORMAT,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, CONF_TEMPERATURE_UNIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import TemperatureConverter

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

DEFAULT_NAME = "Template Climate"

CONF_CURRENT_HUMIDITY = "current_humidity"
CONF_CURRENT_TEMPERATURE = "current_temperature"
CONF_FAN_MODE = "fan_mode"
CONF_FAN_MODES = "fan_modes"
CONF_HVAC_ACTION = "hvac_action"
CONF_HVAC_MODE = "hvac_mode"
CONF_HVAC_MODES = "hvac_modes"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_MIN_TEMP = "min_temp"
CONF_PRESET_MODE = "preset_mode"
CONF_PRESET_MODES = "preset_modes"
CONF_SWING_HORIZONTAL_MODE = "swing_horizontal_mode"
CONF_SWING_HORIZONTAL_MODES = "swing_horizontal_modes"
CONF_SWING_MODE = "swing_mode"
CONF_SWING_MODES = "swing_modes"
CONF_TARGET_HUMIDITY = "target_humidity"
CONF_TARGET_TEMPERATURE = "target_temperature"
CONF_TARGET_TEMPERATURE_HIGH = "target_temperature_high"
CONF_TARGET_TEMPERATURE_LOW = "target_temperature_low"
CONF_TARGET_TEMPERATURE_STEP = "target_temperature_step"

SET_FAN_MODE_ACTION = "set_fan_mode"
SET_HUMIDITY_ACTION = "set_humidity"
SET_HVAC_MODE_ACTION = "set_hvac_mode"
SET_PRESET_MODE_ACTION = "set_preset_mode"
SET_SWING_HORIZONTAL_MODE_ACTION = "set_swing_horizontal_mode"
SET_SWING_MODE_ACTION = "set_swing_mode"
SET_TEMPERATURE_ACTION = "set_temperature"

SCRIPT_FIELDS = (
    SET_FAN_MODE_ACTION,
    SET_HUMIDITY_ACTION,
    SET_HVAC_MODE_ACTION,
    SET_PRESET_MODE_ACTION,
    SET_SWING_HORIZONTAL_MODE_ACTION,
    SET_SWING_MODE_ACTION,
    SET_TEMPERATURE_ACTION,
)

_EXTRA_OPTIMISTIC_OPTIONS = (
    CONF_CURRENT_HUMIDITY,
    CONF_CURRENT_TEMPERATURE,
    CONF_FAN_MODE,
    CONF_HVAC_ACTION,
    CONF_PRESET_MODE,
    CONF_SWING_HORIZONTAL_MODE,
    CONF_SWING_MODE,
    CONF_TARGET_HUMIDITY,
    CONF_TARGET_TEMPERATURE_HIGH,
    CONF_TARGET_TEMPERATURE_LOW,
    CONF_TARGET_TEMPERATURE,
)


def _round_to_step(value: float, step: float) -> float:
    """Round a temperature to the nearest step using half-up midpoint handling."""
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    return float(
        (decimal_value / decimal_step).quantize(0, ROUND_HALF_UP) * decimal_step
    )


CLIMATE_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CURRENT_HUMIDITY): cv.template,
        vol.Optional(CONF_CURRENT_TEMPERATURE): cv.template,
        vol.Optional(CONF_FAN_MODE): cv.template,
        vol.Optional(CONF_FAN_MODES): cv.template,
        vol.Optional(CONF_HVAC_ACTION): cv.template,
        vol.Optional(CONF_HVAC_MODE): cv.template,
        vol.Optional(CONF_HVAC_MODES): cv.template,
        vol.Optional(CONF_MAX_HUMIDITY, default=DEFAULT_MAX_HUMIDITY): vol.Coerce(int),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_HUMIDITY, default=DEFAULT_MIN_HUMIDITY): vol.Coerce(int),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRESET_MODE): cv.template,
        vol.Optional(CONF_PRESET_MODES): cv.template,
        vol.Optional(CONF_SWING_MODE): cv.template,
        vol.Optional(CONF_SWING_MODES): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_HIGH): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_LOW): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_STEP): cv.positive_float,
        vol.Optional(CONF_TARGET_TEMPERATURE): cv.template,
        vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(TemperatureConverter.VALID_UNITS),
        vol.Optional(SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_SWING_HORIZONTAL_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
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


def _string_to_list(result: str) -> list[str]:
    for char in "()[] ":
        result = result.replace(char, "")
    return list(result.split(","))


def hvac_modes_list(
    entity: AbstractTemplateClimate,
) -> Callable[[Any], list[HVACMode] | None]:
    """Convert the result to a list of numbers that represent hue and saturation."""

    expected = f"expected a list of hvac modes: [{', '.join([str(item) for item in HVACMode])}]"

    def convert(result: Any) -> list[HVACMode] | None:
        if template_validators.check_result_for_none(result):
            return None

        if isinstance(result, str):
            with contextlib.suppress(ValueError):
                result = _string_to_list(result)

        if isinstance(result, (list, tuple)) and all(
            isinstance(value, str) for value in result
        ):
            validated = []
            invalid = []
            for item in result:
                if item in HVACMode:
                    validated.append(HVACMode(item))
                else:
                    invalid.append(item)

            if invalid:
                template_validators.log_validation_result_error(
                    entity, CONF_HVAC_MODES, result, expected
                )

            return validated

        template_validators.log_validation_result_error(
            entity, CONF_HVAC_MODES, result, expected
        )
        return None

    return convert


class AbstractTemplateClimate(AbstractTemplateEntity, ClimateEntity):
    """Representation of template climate features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _state_option = CONF_HVAC_MODE
    _extra_optimistic_options = _EXTRA_OPTIMISTIC_OPTIONS

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(  # pylint: disable=super-init-not-called
        self, hass: HomeAssistant, name: str, config: dict[str, Any]
    ) -> None:
        """Initialize the features."""

        self._attr_temperature_unit = (
            config.get(CONF_TEMPERATURE_UNIT) or hass.config.units.temperature_unit
        )
        self._attr_target_temperature_step = config.get(CONF_TARGET_TEMPERATURE_STEP)

        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_min_humidity = config[CONF_MIN_HUMIDITY]
        self._attr_max_humidity = config[CONF_MAX_HUMIDITY]

        self._attr_hvac_mode = None
        self._attr_hvac_modes = []

        self._last_on: HVACMode | None = None

        # Setup HVAC Mode
        self.setup_state_template(
            "_attr_hvac_mode",
            template_validators.strenum(self, CONF_HVAC_MODE, HVACMode),
            self._update_hvac_mode,
        )
        self.setup_template(
            CONF_HVAC_MODES,
            "_attr_hvac_modes",
            hvac_modes_list(self),
            self._update_hvac_modes,
        )
        self.setup_template(
            CONF_HVAC_ACTION,
            "_attr_hvac_action",
            template_validators.strenum(self, CONF_HVAC_ACTION, HVACAction),
        )

        # Temperatures
        self.setup_template(
            CONF_CURRENT_TEMPERATURE,
            "_attr_current_temperature",
            template_validators.number(self, CONF_CURRENT_TEMPERATURE),
        )

        for option, attr in (
            (CONF_TARGET_TEMPERATURE, "_attr_target_temperature"),
            (CONF_TARGET_TEMPERATURE_LOW, "_attr_target_temperature_low"),
            (CONF_TARGET_TEMPERATURE_HIGH, "_attr_target_temperature_high"),
        ):
            self.setup_template(
                option,
                attr,
                template_validators.number(
                    self, option, self._attr_min_temp, self._attr_max_temp
                ),
            )

        # Humidities
        self.setup_template(
            CONF_TARGET_HUMIDITY,
            "_attr_target_humidity",
            template_validators.number(
                self,
                CONF_TARGET_HUMIDITY,
                self._attr_min_humidity,
                self._attr_max_humidity,
                int,
            ),
        )
        self.setup_template(
            CONF_CURRENT_HUMIDITY,
            "_attr_current_humidity",
            template_validators.number(self, CONF_CURRENT_HUMIDITY, 0, 100, int),
        )

        # Fan Mode

        self.setup_template(CONF_FAN_MODE, "_attr_fan_mode", cv.string)
        self.setup_template(
            CONF_FAN_MODES,
            "_attr_fan_modes",
            template_validators.list_of_strings(self, CONF_FAN_MODES),
        )

        # Swing Mode
        self.setup_template(CONF_SWING_MODE, "_attr_swing_mode", cv.string)
        self.setup_template(
            CONF_SWING_MODES,
            "_attr_swing_modes",
            template_validators.list_of_strings(self, CONF_SWING_MODES),
        )

        # Swing Horizontal Mode
        self.setup_template(
            CONF_SWING_HORIZONTAL_MODE, "_attr_swing_horizontal_mode", cv.string
        )
        self.setup_template(
            CONF_SWING_HORIZONTAL_MODES,
            "_attr_swing_horizontal_modes",
            template_validators.list_of_strings(self, CONF_SWING_HORIZONTAL_MODES),
        )

        # Preset Mode
        self.setup_template(CONF_PRESET_MODE, "_attr_preset_mode", cv.string)
        self.setup_template(
            CONF_PRESET_MODES,
            "_attr_preset_modes",
            template_validators.list_of_strings(self, CONF_PRESET_MODES),
        )

        self._attr_supported_features = ClimateEntityFeature(0)
        for action_id, supported_feature in (
            (SET_FAN_MODE_ACTION, ClimateEntityFeature.FAN_MODE),
            (SET_HUMIDITY_ACTION, ClimateEntityFeature.TARGET_HUMIDITY),
            (SET_PRESET_MODE_ACTION, ClimateEntityFeature.PRESET_MODE),
            (
                SET_SWING_HORIZONTAL_MODE_ACTION,
                ClimateEntityFeature.SWING_HORIZONTAL_MODE,
            ),
            (SET_SWING_MODE_ACTION, ClimateEntityFeature.SWING_MODE),
            (
                SET_TEMPERATURE_ACTION,
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
            ),
        ):
            if (action_config := self._config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    def _update_hvac_mode(self, render) -> None:
        self._attr_hvac_mode = render
        if render is not None and render != HVACMode.OFF:
            self._last_on = render

    def _update_hvac_modes(self, render) -> None:
        if isinstance(render, list):
            supported_features = (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )
            if HVACMode.OFF in render:
                self._attr_supported_features |= supported_features
            else:
                self._attr_supported_features &= ~supported_features

        self._attr_hvac_modes = render

    def _update_target_temperature(
        self,
        result,
    ) -> None:
        if result is None:
            self._attr_target_temperature = None
            return

        if self._attr_target_temperature_step is None:
            self._attr_target_temperature = result
        else:
            self._attr_target_temperature = _round_to_step(
                float(result), self._attr_target_temperature_step
            )

    def _update_optimistic_hvac(self, hvac_mode: HVACMode | None) -> None:
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the climate off."""
        if self._attr_hvac_mode is None:
            return

        if self._attr_hvac_mode != HVACMode.OFF:
            self._last_on = self._attr_hvac_mode

        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn the climate on."""
        if (last_on := self._last_on) is not None:
            await self.async_set_hvac_mode(last_on)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        if script := self._action_scripts.get(SET_HVAC_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"hvac_mode": hvac_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._update_optimistic_hvac(hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if script := self._action_scripts.get(SET_PRESET_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"preset_mode": preset_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if script := self._action_scripts.get(SET_FAN_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"fan_mode": fan_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        if script := self._action_scripts.get(SET_SWING_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"swing_mode": swing_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the swing horizontal mode."""
        if script := self._action_scripts.get(SET_SWING_HORIZONTAL_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"swing_horizontal_mode": swing_horizontal_mode},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        if script := self._action_scripts.get(SET_HUMIDITY_ACTION):
            await self.async_run_script(
                script,
                run_variables={"humidity": humidity},
                context=self._context,
            )

        if self._attr_assumed_state:
            self._attr_target_humidity = humidity
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set one or more target temperatures."""
        common_params: dict[str, Any] = {}
        write_state = False
        if (attr := kwargs.get(ATTR_TEMPERATURE)) is not None and (
            temperature := template_validators.number(
                self,
                f"{SET_TEMPERATURE_ACTION} {ATTR_TEMPERATURE}",
                self._attr_min_temp,
                self._attr_max_temp,
            )(attr)
        ) is not None:
            common_params["temperature"] = temperature
            if self._attr_assumed_state:
                self._attr_target_temperature = temperature
                write_state = True

        if (attr := kwargs.get(ATTR_TARGET_TEMP_HIGH)) and (
            target_temp_high := template_validators.number(
                self,
                f"{SET_TEMPERATURE_ACTION} {ATTR_TARGET_TEMP_HIGH}",
                self._attr_min_temp,
                self._attr_max_temp,
            )(attr)
        ) is not None:
            common_params["target_temp_high"] = target_temp_high
            if self._attr_assumed_state:
                self._attr_target_temperature_high = target_temp_high
                write_state = True

        if (attr := kwargs.get(ATTR_TARGET_TEMP_LOW)) and (
            target_temp_low := template_validators.number(
                self,
                f"{SET_TEMPERATURE_ACTION} {ATTR_TARGET_TEMP_LOW}",
                self._attr_min_temp,
                self._attr_max_temp,
            )(attr)
        ) is not None:
            common_params["target_temp_low"] = target_temp_low
            if self._attr_assumed_state:
                self._attr_target_temperature_low = target_temp_low
                write_state = True

        breadcrumb = f"{SET_TEMPERATURE_ACTION} {ATTR_HVAC_MODE}"
        if (attr := kwargs.get(ATTR_HVAC_MODE)) and (
            hvac_mode := template_validators.strenum(self, breadcrumb, HVACMode)(attr)
        ) is not None:
            if hvac_mode in self._attr_hvac_modes:
                common_params["hvac_mode"] = hvac_mode
                if self._attr_assumed_state:
                    self._attr_hvac_mode = hvac_mode
                    write_state = True
            else:
                template_validators.log_validation_result_error(
                    self,
                    breadcrumb,
                    hvac_mode.value,
                    tuple([str(mode) for mode in self._attr_hvac_modes]),
                )

        if script := self._action_scripts.get(SET_TEMPERATURE_ACTION):
            await self.async_run_script(
                script,
                run_variables=common_params,
                context=self._context,
            )

        if write_state:
            self.async_write_ha_state()


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
