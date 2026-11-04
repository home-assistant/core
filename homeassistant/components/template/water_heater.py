"""Support for Template water heaters."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Self, override

import probatio

from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    ENTITY_ID_FORMAT,
    WaterHeaterCapabilityAttribute,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    WaterHeaterStateAttribute,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_TEMPERATURE_UNIT, PRECISION_TENTHS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import TemperatureConverter

from . import validators as tcv
from .const import CONF_TURN_OFF, CONF_TURN_ON, DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DEFAULT_NAME = "Template Water Heater"

CONF_AWAY_MODE = "away_mode"
CONF_CURRENT_TEMPERATURE = "current_temperature"
CONF_MAX_TEMPERATURE = "max_temperature"
CONF_MIN_TEMPERATURE = "min_temperature"
CONF_OPERATION_LIST = "operation_list"
CONF_OPERATION_MODE = "operation_mode"
CONF_TARGET_TEMPERATURE = "target_temperature"
CONF_TARGET_TEMPERATURE_STEP = "target_temperature_step"

SET_OPERATION_MODE_ACTION = "set_operation_mode"
SET_TEMPERATURE_ACTION = "set_temperature"
TURN_AWAY_MODE_OFF_ACTION = "turn_away_mode_off"
TURN_AWAY_MODE_ON_ACTION = "turn_away_mode_on"

SCRIPT_FIELDS = (
    CONF_TURN_OFF,
    CONF_TURN_ON,
    SET_OPERATION_MODE_ACTION,
    SET_TEMPERATURE_ACTION,
    TURN_AWAY_MODE_OFF_ACTION,
    TURN_AWAY_MODE_ON_ACTION,
)


_BLOCKED_ATTRIBUTES = tcv.BlockedTemplateAttributes(
    attributes=(WaterHeaterCapabilityAttribute, WaterHeaterStateAttribute)
)


def _round_to_step(value: float, step: float) -> float:
    """Round a temperature to the nearest step using half-up midpoint handling."""
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    return float(
        (decimal_value / decimal_step).quantize(0, ROUND_HALF_UP) * decimal_step
    )


WATER_HEATER_COMMON_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_AWAY_MODE): cv.template,
        probatio.Optional(CONF_CURRENT_TEMPERATURE): cv.template,
        probatio.Optional(CONF_MAX_TEMPERATURE): probatio.Coerce(float),
        probatio.Optional(CONF_MIN_TEMPERATURE): probatio.Coerce(float),
        probatio.Required(CONF_OPERATION_LIST): cv.template,
        probatio.Optional(CONF_OPERATION_MODE): cv.template,
        probatio.Optional(CONF_TARGET_TEMPERATURE): cv.template,
        probatio.Optional(CONF_TARGET_TEMPERATURE_STEP): probatio.All(
            probatio.Coerce(float), probatio.Range(min=PRECISION_TENTHS)
        ),
        probatio.Optional(CONF_TEMPERATURE_UNIT): probatio.In(
            TemperatureConverter.VALID_UNITS
        ),
        probatio.Required(SET_OPERATION_MODE_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(CONF_TURN_OFF, "on_off_actions"): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(CONF_TURN_ON, "on_off_actions"): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(
            TURN_AWAY_MODE_OFF_ACTION, "away_mode_actions"
        ): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(
            TURN_AWAY_MODE_ON_ACTION, "away_mode_actions"
        ): cv.SCRIPT_SCHEMA,
    },
)

_WATER_HEATER_VALIDATION = (
    tcv.requires_option(CONF_TARGET_TEMPERATURE, SET_TEMPERATURE_ACTION),
    tcv.requires_option(CONF_AWAY_MODE, TURN_AWAY_MODE_ON_ACTION),
)


WATER_HEATER_YAML_SCHEMA = probatio.All(
    WATER_HEATER_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA).extend(
        make_template_entity_common_schema(
            WATER_HEATER_DOMAIN,
            DEFAULT_NAME,
            _BLOCKED_ATTRIBUTES,
        ).schema
    ),
    *_WATER_HEATER_VALIDATION,
)

WATER_HEATER_CONFIG_ENTRY_SCHEMA = probatio.All(
    WATER_HEATER_COMMON_SCHEMA.extend(
        TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
    ),
    *_WATER_HEATER_VALIDATION,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template water heaters."""
    await async_setup_template_platform(
        hass,
        WATER_HEATER_DOMAIN,
        config,
        StateWaterHeaterEntity,
        TriggerWaterHeaterEntity,
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
        StateWaterHeaterEntity,
        WATER_HEATER_CONFIG_ENTRY_SCHEMA,
        script_options=SCRIPT_FIELDS,
    )


@callback
def async_create_preview_water_heater(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateWaterHeaterEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateWaterHeaterEntity,
        WATER_HEATER_CONFIG_ENTRY_SCHEMA,
    )


@dataclass(kw_only=True)
class WaterHeaterExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    current_operation: str | None
    current_temperature: float | None
    is_away_mode_on: bool | None
    operation_list: list[str] | None
    target_temperature: float | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the extra data."""
        return {
            "current_operation": self.current_operation,
            "current_temperature": self.current_temperature,
            "is_away_mode_on": self.is_away_mode_on,
            "operation_list": self.operation_list,
            "target_temperature": self.target_temperature,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored state from a dict."""
        try:
            return cls(
                current_operation=restored["current_operation"],
                current_temperature=restored["current_temperature"],
                is_away_mode_on=restored["is_away_mode_on"],
                operation_list=restored["operation_list"],
                target_temperature=restored["target_temperature"],
            )
        except KeyError:
            return None


class AbstractTemplateWaterHeater(
    AbstractTemplateEntity, WaterHeaterEntity, RestoreEntity
):
    """Representation of template water heater features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _state_option = CONF_OPERATION_MODE
    _restore_state_extra_data = WaterHeaterExtraStoredData
    _restore_state_properties = ("_attr_current_operation",)
    _blocked_attributes = _BLOCKED_ATTRIBUTES

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(  # pylint: disable=super-init-not-called
        self, hass: HomeAssistant, name: str, config: dict[str, Any]
    ) -> None:
        """Initialize the features."""

        self._attr_native_temperature_unit = (
            config.get(CONF_TEMPERATURE_UNIT) or hass.config.units.temperature_unit
        )
        self._attr_target_temperature_step = config.get(CONF_TARGET_TEMPERATURE_STEP)

        # Only set these options when it exists in the configuration in order
        # to properly use default values set by the upstream class.
        for attr, option in (
            ("_attr_max_temp", CONF_MAX_TEMPERATURE),
            ("_attr_min_temp", CONF_MIN_TEMPERATURE),
        ):
            if (option_value := config.get(option)) is not None:
                setattr(self, attr, option_value)

        self._attr_current_operation = None
        self._attr_operation_list = []
        self._attr_native_target_temperature = None
        self._attr_is_away_mode_on = None

        self.setup_template(
            CONF_OPERATION_LIST,
            "_attr_operation_list",
            tcv.list_of_strings(self, CONF_OPERATION_LIST),
            none_on_template_error=False,
        )
        self.setup_state_template(
            "_attr_current_operation",
            tcv.item_in_list(
                self,
                CONF_OPERATION_MODE,
                "_attr_operation_list",
                CONF_OPERATION_LIST,
                stringify_result=True,
            ),
        )

        self.setup_template(
            CONF_CURRENT_TEMPERATURE,
            "_attr_native_current_temperature",
            tcv.number(self, CONF_CURRENT_TEMPERATURE),
        )
        self.setup_template(
            CONF_TARGET_TEMPERATURE,
            "_attr_native_target_temperature",
            tcv.number(self, CONF_TARGET_TEMPERATURE, self.min_temp, self.max_temp),
            on_update=self._update_target_temperature,
        )
        self.add_assumed_attribute(
            "_attr_native_target_temperature",
            CONF_TARGET_TEMPERATURE,
            SET_TEMPERATURE_ACTION,
        )

        self.setup_template(
            CONF_AWAY_MODE,
            "_attr_is_away_mode_on",
            tcv.boolean(self, CONF_AWAY_MODE),
        )
        self.add_assumed_attribute(
            "_attr_is_away_mode_on", CONF_AWAY_MODE, TURN_AWAY_MODE_ON_ACTION
        )

        self._attr_supported_features = WaterHeaterEntityFeature(0)
        for action_id, supported_feature in (
            (CONF_TURN_OFF, WaterHeaterEntityFeature.ON_OFF),
            (CONF_TURN_ON, 0),
            (SET_OPERATION_MODE_ACTION, WaterHeaterEntityFeature.OPERATION_MODE),
            (SET_TEMPERATURE_ACTION, WaterHeaterEntityFeature.TARGET_TEMPERATURE),
            (TURN_AWAY_MODE_OFF_ACTION, WaterHeaterEntityFeature.AWAY_MODE),
            (TURN_AWAY_MODE_ON_ACTION, 0),
        ):
            if (action_config := self._config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    def _round_temperature_value(self, value: Any) -> float:
        if self._attr_target_temperature_step is None:
            return value
        rounded = _round_to_step(float(value), self._attr_target_temperature_step)
        return min(self.max_temp, max(self.min_temp, rounded))

    def _update_target_temperature(self, result: Any) -> None:
        if result is None:
            self._attr_native_target_temperature = None
            return

        self._attr_native_target_temperature = self._round_temperature_value(result)

    async def _async_set_operation_mode(self, operation_mode: str) -> None:
        if script := self._action_scripts.get(SET_OPERATION_MODE_ACTION):
            await self.async_run_script(
                script,
                run_variables={"operation_mode": operation_mode},
                context=self._context,
            )

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self._async_set_operation_mode(operation_mode)

        if self._attr_assumed_state:
            self._attr_current_operation = operation_mode
            self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        write_state = False

        if (operation_mode := kwargs.get("operation_mode")) is not None:
            await self.async_handle_set_operation_mode(operation_mode)

        if (value := kwargs.get("temperature")) is not None and (
            validated := tcv.number(
                self,
                f"{SET_TEMPERATURE_ACTION} temperature",
                self.min_temp,
                self.max_temp,
            )(value)
        ) is not None:
            rounded = self._round_temperature_value(validated)
            if script := self._action_scripts.get(SET_TEMPERATURE_ACTION):
                await self.async_run_script(
                    script,
                    run_variables={
                        "temperature": rounded,
                        "operation_mode": operation_mode,
                    },
                    context=self._context,
                )

                if self.update_assumed_attribute(CONF_TARGET_TEMPERATURE, rounded):
                    write_state = True

        if write_state:
            self.async_write_ha_state()

    @override
    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        if script := self._action_scripts.get(TURN_AWAY_MODE_ON_ACTION):
            await self.async_run_script(script, context=self._context)

        self.write_assumed_attribute(CONF_AWAY_MODE, True)

    @override
    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        if script := self._action_scripts.get(TURN_AWAY_MODE_OFF_ACTION):
            await self.async_run_script(script, context=self._context)

        self.write_assumed_attribute(CONF_AWAY_MODE, False)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater on."""
        if script := self._action_scripts.get(CONF_TURN_ON):
            await self.async_run_script(script, context=self._context)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater off."""
        if script := self._action_scripts.get(CONF_TURN_OFF):
            await self.async_run_script(script, context=self._context)

    @property
    @override
    def extra_restore_state_data(self) -> WaterHeaterExtraStoredData:
        """Return water heater specific state data to be restored."""
        return WaterHeaterExtraStoredData(
            current_operation=self._attr_current_operation,
            current_temperature=self._attr_native_current_temperature,
            is_away_mode_on=self._attr_is_away_mode_on,
            operation_list=self._attr_operation_list,
            target_temperature=self._attr_native_target_temperature,
        )

    @override
    def restore_extra_data(self, extra_data: WaterHeaterExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_current_operation = extra_data.current_operation
        self._attr_native_current_temperature = extra_data.current_temperature
        self._attr_is_away_mode_on = extra_data.is_away_mode_on
        self._attr_operation_list = extra_data.operation_list or []
        self._attr_native_target_temperature = extra_data.target_temperature


class StateWaterHeaterEntity(TemplateEntity, AbstractTemplateWaterHeater):
    """Representation of a state-based template water heater."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the state-based template water heater."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateWaterHeater.__init__(self, hass, name, config)


class TriggerWaterHeaterEntity(TriggerEntity, AbstractTemplateWaterHeater):
    """Representation of a trigger-based template water heater."""

    domain = WATER_HEATER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the trigger-based template water heater."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateWaterHeater.__init__(self, hass, name, config)
