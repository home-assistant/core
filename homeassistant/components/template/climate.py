"""Support for climates which integrate with other components."""

from __future__ import annotations

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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
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

# Legacy YAML key, analogous to cover's CONF_COVERS
CONF_THERMOSTATS = "thermostats"

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

# Legacy platform schema: { climate: { platform: template, thermostats: {...} } }
PLATFORM_SCHEMA = CLIMATE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_THERMOSTATS): cv.schema_with_slug_keys(
            CLIMATE_LEGACY_YAML_SCHEMA
        )
    }
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
        legacy_key=CONF_THERMOSTATS,
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

    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        # Keep typed as list[HVACMode] for mypy/ClimateEntity
        raw_hvac_modes = config.get(CONF_HVAC_MODES, [HVACMode.AUTO])
        self._attr_hvac_modes = [
            m if isinstance(m, HVACMode) else HVACMode(str(m).lower().strip())
            for m in raw_hvac_modes
        ]

        # Other mode lists are strings
        self._attr_fan_modes = [str(m) for m in config.get(CONF_FAN_MODES, [])]
        self._attr_swing_modes = [str(m) for m in config.get(CONF_SWING_MODES, [])]
        self._attr_preset_modes = [str(m) for m in config.get(CONF_PRESET_MODES, [])]

        self._attr_max_temp = config[CONF_MAX_TEMP]
        self._attr_min_temp = config[CONF_MIN_TEMP]
        self._attr_max_humidity = config[CONF_MAX_HUMIDITY]
        self._attr_min_humidity = config[CONF_MIN_HUMIDITY]
        self._attr_target_temperature_step = config.get(CONF_TEMP_STEP)
        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )
        self._attr_precision = config.get(CONF_PRECISION, DEFAULT_PRECISION)

        # hvac_mode: convert -> HVACMode then enforce within hvac_modes
        _hvac_mode_to_enum = template_validators.strenum(
            self,
            CONF_HVAC_MODE,
            HVACMode,
            none_on_unknown_unavailable=True,
        )
        _hvac_mode_in_list = template_validators.item_in_list(
            self,
            CONF_HVAC_MODE,
            self._attr_hvac_modes,
            items_attribute=CONF_HVAC_MODES,
            none_on_unknown_unavailable=True,
        )

        def _validate_hvac_mode(result: Any) -> HVACMode | None:
            mode = _hvac_mode_to_enum(result)
            if mode is None:
                return None
            return _hvac_mode_in_list(mode)

        self.setup_template(
            CONF_HVAC_MODE,
            "_attr_hvac_mode",
            _validate_hvac_mode,
        )

        self.setup_template(
            CONF_HVAC_ACTION,
            "_attr_hvac_action",
            template_validators.strenum(
                self,
                CONF_HVAC_ACTION,
                HVACAction,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_CURRENT_TEMPERATURE,
            "_attr_current_temperature",
            template_validators.number(
                self,
                CONF_CURRENT_TEMPERATURE,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE,
            "_attr_target_temperature",
            template_validators.number(
                self,
                CONF_TARGET_TEMPERATURE,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE_HIGH,
            "_attr_target_temperature_high",
            template_validators.number(
                self,
                CONF_TARGET_TEMPERATURE_HIGH,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE_LOW,
            "_attr_target_temperature_low",
            template_validators.number(
                self,
                CONF_TARGET_TEMPERATURE_LOW,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_FAN_MODE,
            "_attr_fan_mode",
            template_validators.item_in_list(
                self,
                CONF_FAN_MODE,
                self._attr_fan_modes,
                items_attribute=CONF_FAN_MODES,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_SWING_MODE,
            "_attr_swing_mode",
            template_validators.item_in_list(
                self,
                CONF_SWING_MODE,
                self._attr_swing_modes,
                items_attribute=CONF_SWING_MODES,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_PRESET_MODE,
            "_attr_preset_mode",
            template_validators.item_in_list(
                self,
                CONF_PRESET_MODE,
                self._attr_preset_modes,
                items_attribute=CONF_PRESET_MODES,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_HUMIDITY,
            "_attr_current_humidity",
            template_validators.number(
                self,
                CONF_HUMIDITY,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )
        self.setup_template(
            CONF_TARGET_HUMIDITY,
            "_attr_target_humidity",
            template_validators.number(
                self,
                CONF_TARGET_HUMIDITY,
                return_type=float,
                none_on_unknown_unavailable=True,
            ),
        )

        self._attr_supported_features = ClimateEntityFeature(0)

        if (action_cfg := config.get(SET_HVAC_MODE_ACTION)) is not None:
            self.add_script(SET_HVAC_MODE_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

        if (action_cfg := config.get(SET_TEMPERATURE_ACTION)) is not None:
            self.add_script(SET_TEMPERATURE_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            if (
                config.get(CONF_TARGET_TEMPERATURE_HIGH) is not None
                or config.get(CONF_TARGET_TEMPERATURE_LOW) is not None
            ):
                self._attr_supported_features |= (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )

        if (action_cfg := config.get(SET_FAN_MODE_ACTION)) is not None:
            self.add_script(SET_FAN_MODE_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        if (action_cfg := config.get(SET_SWING_MODE_ACTION)) is not None:
            self.add_script(SET_SWING_MODE_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        if (action_cfg := config.get(SET_PRESET_MODE_ACTION)) is not None:
            self.add_script(SET_PRESET_MODE_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        if (action_cfg := config.get(SET_HUMIDITY_ACTION)) is not None:
            self.add_script(SET_HUMIDITY_ACTION, action_cfg, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

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
        run_variables: dict[str, Any] = {}

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
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateClimate.__init__(self, name, config)


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
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateClimate.__init__(self, name, config)
