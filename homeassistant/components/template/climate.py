"""Support for climates which integrate with other components."""

from __future__ import annotations

from collections.abc import Generator, Sequence
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import TriggerUpdateCoordinator
from .const import DOMAIN
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_AVAILABILITY = "availability"

CONF_HVAC_MODE = "hvac_mode"
CONF_HVAC_ACTION = "hvac_action"
CONF_CURRENT_TEMPERATURE = "current_temperature"
CONF_TARGET_TEMPERATURE = "target_temperature"
CONF_TARGET_TEMPERATURE_HIGH = "target_temperature_high"
CONF_TARGET_TEMPERATURE_LOW = "target_temperature_low"
CONF_FAN_MODE = "fan_mode"
CONF_SWING_MODE = "swing_mode"
CONF_PRESET_MODE = "preset_mode"
CONF_HUMIDITY = "humidity"
CONF_TARGET_HUMIDITY = "target_humidity"

CONF_HVAC_MODES = "hvac_modes"
CONF_FAN_MODES = "fan_modes"
CONF_SWING_MODES = "swing_modes"
CONF_PRESET_MODES = "preset_modes"

CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_PRECISION = "precision"
CONF_TEMP_STEP = "temp_step"

SET_HVAC_MODE_ACTION = "set_hvac_mode"
SET_PRESET_MODE_ACTION = "set_preset_mode"
SET_FAN_MODE_ACTION = "set_fan_mode"
SET_SWING_MODE_ACTION = "set_swing_mode"
SET_TEMPERATURE_ACTION = "set_temperature"
SET_HUMIDITY_ACTION = "set_humidity"

DEFAULT_NAME = "Template Climate"
DEFAULT_TEMP_MIN = 7
DEFAULT_TEMP_MAX = 35
DEFAULT_HUMIDITY_MIN = 30
DEFAULT_HUMIDITY_MAX = 99
DEFAULT_PRECISION = PRECISION_TENTHS


LEGACY_FIELDS = {
    CONF_VALUE_TEMPLATE: CONF_HVAC_MODE,
}

CLIMATE_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HVAC_MODE): cv.template,
        vol.Optional(CONF_HVAC_ACTION): cv.template,
        vol.Optional(CONF_CURRENT_TEMPERATURE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_HIGH): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_LOW): cv.template,
        vol.Optional(CONF_FAN_MODE): cv.template,
        vol.Optional(CONF_SWING_MODE): cv.template,
        vol.Optional(CONF_PRESET_MODE): cv.template,
        vol.Optional(CONF_HUMIDITY): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY): cv.template,
        vol.Optional(SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_HVAC_MODES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_FAN_MODES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SWING_MODES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PRESET_MODES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_MAX_TEMP, default=DEFAULT_TEMP_MAX): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP, default=DEFAULT_TEMP_MIN): vol.Coerce(float),
        vol.Optional(CONF_MAX_HUMIDITY, default=DEFAULT_HUMIDITY_MAX): vol.Coerce(
            float
        ),
        vol.Optional(CONF_MIN_HUMIDITY, default=DEFAULT_HUMIDITY_MIN): vol.Coerce(
            float
        ),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_TEMP_STEP): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
    }
)

CLIMATE_YAML_SCHEMA = vol.All(
    vol.Schema({})
    .extend(CLIMATE_COMMON_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA)
    .extend(
        make_template_entity_common_modern_schema(CLIMATE_DOMAIN, DEFAULT_NAME).schema
    ),
    cv.has_at_least_one_key(
        SET_HVAC_MODE_ACTION,
        SET_PRESET_MODE_ACTION,
        SET_FAN_MODE_ACTION,
        SET_SWING_MODE_ACTION,
        SET_TEMPERATURE_ACTION,
        SET_HUMIDITY_ACTION,
    ),
)

CLIMATE_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(CLIMATE_COMMON_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA),
)

PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {vol.Required(CLIMATE_DOMAIN): cv.schema_with_slug_keys(CLIMATE_LEGACY_YAML_SCHEMA)}
)

CLIMATE_CONFIG_ENTRY_SCHEMA = vol.All(
    CLIMATE_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template climate."""
    await async_setup_template_platform(
        hass,
        CLIMATE_DOMAIN,
        config,
        StateClimateEntity,
        TriggerClimateEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CLIMATE_DOMAIN,
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
        True,
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
        True,
    )


class AbstractTemplateClimate(AbstractTemplateEntity, ClimateEntity):
    """Representation of a template climate features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _extra_optimistic_options = (
        CONF_HVAC_MODE,
        CONF_FAN_MODE,
        CONF_SWING_MODE,
        CONF_PRESET_MODE,
    )

    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._attr_hvac_mode = None
        self._attr_hvac_action = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_fan_mode = None
        self._attr_swing_mode = None
        self._attr_preset_mode = None
        self._attr_current_humidity = None
        self._attr_target_humidity = None

        self._attr_hvac_modes = config.get(CONF_HVAC_MODES, [HVACMode.AUTO])
        self._attr_fan_modes = config.get(CONF_FAN_MODES, [])
        self._attr_swing_modes = config.get(CONF_SWING_MODES, [])
        self._attr_preset_modes = config.get(CONF_PRESET_MODES, [])
        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_humidity = config[CONF_MAX_HUMIDITY]
        self._attr_min_humidity = config[CONF_MIN_HUMIDITY]
        self._attr_target_temperature_step = config.get(CONF_TEMP_STEP)
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )
        self._attr_precision = config.get(CONF_PRECISION, DEFAULT_PRECISION)
        self._hvac_mode_template = config.get(CONF_HVAC_MODE)
        self._hvac_action_template = config.get(CONF_HVAC_ACTION)
        self._current_temp_template = config.get(CONF_CURRENT_TEMPERATURE)
        self._target_temp_template = config.get(CONF_TARGET_TEMPERATURE)
        self._target_temp_high_template = config.get(CONF_TARGET_TEMPERATURE_HIGH)
        self._target_temp_low_template = config.get(CONF_TARGET_TEMPERATURE_LOW)
        self._fan_mode_template = config.get(CONF_FAN_MODE)
        self._swing_mode_template = config.get(CONF_SWING_MODE)
        self._preset_mode_template = config.get(CONF_PRESET_MODE)
        self._humidity_template = config.get(CONF_HUMIDITY)
        self._target_humidity_template = config.get(CONF_TARGET_HUMIDITY)

        self._attr_supported_features = ClimateEntityFeature(0)

        if config.get(SET_TEMPERATURE_ACTION):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            if (
                self._target_temp_high_template is not None
                or self._target_temp_low_template is not None
            ):
                self._attr_supported_features |= (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )

        if config.get(SET_FAN_MODE_ACTION):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if config.get(SET_SWING_MODE_ACTION):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if config.get(SET_PRESET_MODE_ACTION):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        if config.get(SET_HUMIDITY_ACTION):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

        if config.get(SET_HVAC_MODE_ACTION):
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    def _iterate_scripts(
        self, config: dict[str, Any]
    ) -> Generator[tuple[str, Sequence[dict[str, Any]]]]:
        """Iterate over the action scripts."""
        for action_id in (
            SET_HVAC_MODE_ACTION,
            SET_PRESET_MODE_ACTION,
            SET_FAN_MODE_ACTION,
            SET_SWING_MODE_ACTION,
            SET_TEMPERATURE_ACTION,
            SET_HUMIDITY_ACTION,
        ):
            if (action_config := config.get(action_id)) is not None:
                yield (action_id, action_config)

    @callback
    def _update_hvac_mode(self, result):
        if result is None or result == "None":
            self._attr_hvac_mode = None
            return
        if result in self._attr_hvac_modes:
            self._attr_hvac_mode = result
        else:
            _LOGGER.error(
                "Received invalid hvac_mode: %s. Expected one of: %s",
                result,
                self._attr_hvac_modes,
            )
            self._attr_hvac_mode = None

    @callback
    def _update_hvac_action(self, result):
        if result is None:
            self._attr_hvac_action = None
            return
        try:
            self._attr_hvac_action = HVACAction(str(result))
        except ValueError:
            _LOGGER.warning(
                "Invalid hvac_action value received: %s. Expected one of %s",
                result,
                [m.value for m in HVACAction],
            )
            self._attr_hvac_action = None

    @callback
    def _update_current_temperature(self, result):
        try:
            self._attr_current_temperature = float(result)
        except (ValueError, TypeError):
            self._attr_current_temperature = None

    @callback
    def _update_target_temperature(self, result):
        try:
            self._attr_target_temperature = float(result)
        except (ValueError, TypeError):
            self._attr_target_temperature = None

    @callback
    def _update_target_temperature_high(self, result):
        try:
            self._attr_target_temperature_high = float(result)
        except (ValueError, TypeError):
            self._attr_target_temperature_high = None

    @callback
    def _update_target_temperature_low(self, result):
        try:
            self._attr_target_temperature_low = float(result)
        except (ValueError, TypeError):
            self._attr_target_temperature_low = None

    @callback
    def _update_fan_mode(self, result):
        if result in self._attr_fan_modes:
            self._attr_fan_mode = result
        else:
            self._attr_fan_mode = None

    @callback
    def _update_swing_mode(self, result):
        if result in self._attr_swing_modes:
            self._attr_swing_mode = result
        else:
            self._attr_swing_mode = None

    @callback
    def _update_preset_mode(self, result):
        if result in self._attr_preset_modes:
            self._attr_preset_mode = result
        else:
            self._attr_preset_mode = None

    @callback
    def _update_humidity(self, result):
        try:
            self._attr_current_humidity = float(result)
        except (ValueError, TypeError):
            self._attr_current_humidity = None

    @callback
    def _update_target_humidity(self, result):
        try:
            self._attr_target_humidity = float(result)
        except (ValueError, TypeError):
            self._attr_target_humidity = None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        if script := self._action_scripts.get(SET_HVAC_MODE_ACTION):
            await self.async_run_script(
                script, run_variables={ATTR_HVAC_MODE: hvac_mode}, context=self._context
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        self._attr_preset_mode = preset_mode
        if script := self._action_scripts.get(SET_PRESET_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={ATTR_PRESET_MODE: preset_mode},
                context=self._context,
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._attr_fan_mode = fan_mode
        if script := self._action_scripts.get(SET_FAN_MODE_ACTION):
            await self.async_run_script(
                script, run_variables={ATTR_FAN_MODE: fan_mode}, context=self._context
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        self._attr_swing_mode = swing_mode
        if script := self._action_scripts.get(SET_SWING_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={ATTR_SWING_MODE: swing_mode},
                context=self._context,
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        run_variables = {}
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            run_variables[ATTR_TEMPERATURE] = temperature
        if (temp_low := kwargs.get(ATTR_TARGET_TEMP_LOW)) is not None:
            self._attr_target_temperature_low = temp_low
            run_variables[ATTR_TARGET_TEMP_LOW] = temp_low
        if (temp_high := kwargs.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            self._attr_target_temperature_high = temp_high
            run_variables[ATTR_TARGET_TEMP_HIGH] = temp_high
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._attr_hvac_mode = hvac_mode
            run_variables[ATTR_HVAC_MODE] = hvac_mode

        if script := self._action_scripts.get(SET_TEMPERATURE_ACTION):
            await self.async_run_script(
                script, run_variables=run_variables, context=self._context
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self._attr_target_humidity = humidity
        if script := self._action_scripts.get(SET_HUMIDITY_ACTION):
            await self.async_run_script(
                script, run_variables={ATTR_HUMIDITY: humidity}, context=self._context
            )
        if self._attr_assumed_state:
            self.async_write_ha_state()


class StateClimateEntity(TemplateEntity, AbstractTemplateClimate):
    """Representation of a Template Climate."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the Template Climate."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateClimate.__init__(self, config)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        for action_id, action_config in self._iterate_scripts(config):
            self.add_script(action_id, action_config, name, DOMAIN)

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        template_map = {
            "_attr_hvac_mode": (self._hvac_mode_template, self._update_hvac_mode),
            "_attr_hvac_action": (self._hvac_action_template, self._update_hvac_action),
            "_attr_current_temperature": (
                self._current_temp_template,
                self._update_current_temperature,
            ),
            "_attr_target_temperature": (
                self._target_temp_template,
                self._update_target_temperature,
            ),
            "_attr_target_temperature_high": (
                self._target_temp_high_template,
                self._update_target_temperature_high,
            ),
            "_attr_target_temperature_low": (
                self._target_temp_low_template,
                self._update_target_temperature_low,
            ),
            "_attr_fan_mode": (self._fan_mode_template, self._update_fan_mode),
            "_attr_swing_mode": (self._swing_mode_template, self._update_swing_mode),
            "_attr_preset_mode": (
                self._preset_mode_template,
                self._update_preset_mode,
            ),
            "_attr_current_humidity": (
                self._humidity_template,
                self._update_humidity,
            ),
            "_attr_target_humidity": (
                self._target_humidity_template,
                self._update_target_humidity,
            ),
        }

        for attr, (tpl, updater) in template_map.items():
            if tpl:
                self.add_template_attribute(
                    attr, tpl, None, updater, none_on_template_error=True
                )

        super()._async_setup_templates()


class TriggerClimateEntity(TriggerEntity, AbstractTemplateClimate):
    """Climate entity based on trigger data."""

    domain = CLIMATE_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateClimate.__init__(self, config)

        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        for action_id, action_config in self._iterate_scripts(config):
            self.add_script(action_id, action_config, name, DOMAIN)

        render_keys = [
            (CONF_HVAC_MODE, CONF_HVAC_MODE),
            (CONF_HVAC_ACTION, CONF_HVAC_ACTION),
            (CONF_CURRENT_TEMPERATURE, ATTR_TEMPERATURE),
            (CONF_TARGET_TEMPERATURE, ATTR_TEMPERATURE),
            (CONF_TARGET_TEMPERATURE_HIGH, ATTR_TARGET_TEMP_HIGH),
            (CONF_TARGET_TEMPERATURE_LOW, ATTR_TARGET_TEMP_LOW),
            (CONF_FAN_MODE, CONF_FAN_MODE),
            (CONF_SWING_MODE, CONF_SWING_MODE),
            (CONF_PRESET_MODE, CONF_PRESET_MODE),
            (CONF_HUMIDITY, ATTR_HUMIDITY),
        ]

        for config_key, _ in render_keys:
            if isinstance(config.get(config_key), template.Template):
                self._to_render_simple.append(config_key)
                self._parse_result.add(config_key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False

        update_map = {
            CONF_HVAC_MODE: self._update_hvac_mode,
            CONF_HVAC_ACTION: self._update_hvac_action,
            CONF_CURRENT_TEMPERATURE: self._update_current_temperature,
            CONF_TARGET_TEMPERATURE: self._update_target_temperature,
            CONF_TARGET_TEMPERATURE_HIGH: self._update_target_temperature_high,
            CONF_TARGET_TEMPERATURE_LOW: self._update_target_temperature_low,
            CONF_FAN_MODE: self._update_fan_mode,
            CONF_SWING_MODE: self._update_swing_mode,
            CONF_PRESET_MODE: self._update_preset_mode,
            CONF_HUMIDITY: self._update_humidity,
        }

        for config_key, updater in update_map.items():
            if (rendered := self._rendered.get(config_key)) is not None:
                updater(rendered)
                write_ha_state = True

        if not self._attr_assumed_state or (
            self._attr_assumed_state and len(self._rendered) > 0
        ):
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
