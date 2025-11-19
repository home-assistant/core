"""Support for Template vacuums."""

from __future__ import annotations

from collections.abc import Generator
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    template,
)
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = "vacuums"
CONF_BATTERY_LEVEL = "battery_level"
CONF_BATTERY_LEVEL_TEMPLATE = "battery_level_template"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_FAN_SPEED = "fan_speed"
CONF_FAN_SPEED_TEMPLATE = "fan_speed_template"

DEFAULT_NAME = "Template Vacuum"

ENTITY_ID_FORMAT = VACUUM_DOMAIN + ".{}"
_VALID_STATES = [
    VacuumActivity.CLEANING,
    VacuumActivity.DOCKED,
    VacuumActivity.PAUSED,
    VacuumActivity.IDLE,
    VacuumActivity.RETURNING,
    VacuumActivity.ERROR,
]

LEGACY_FIELDS = {
    CONF_BATTERY_LEVEL_TEMPLATE: CONF_BATTERY_LEVEL,
    CONF_FAN_SPEED_TEMPLATE: CONF_FAN_SPEED,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}

VACUUM_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BATTERY_LEVEL): cv.template,
        vol.Optional(CONF_FAN_SPEED_LIST, default=[]): cv.ensure_list,
        vol.Optional(CONF_FAN_SPEED): cv.template,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,
        vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
        vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
    }
)

VACUUM_YAML_SCHEMA = VACUUM_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA
).extend(
    make_template_entity_common_modern_attributes_schema(
        VACUUM_DOMAIN, DEFAULT_NAME
    ).schema
)

VACUUM_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_FAN_SPEED_LIST, default=[]): cv.ensure_list,
            vol.Optional(CONF_FAN_SPEED_TEMPLATE): cv.template,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,
            vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
            vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_VACUUMS): cv.schema_with_slug_keys(VACUUM_LEGACY_YAML_SCHEMA)}
)

VACUUM_CONFIG_ENTRY_SCHEMA = VACUUM_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template vacuum."""
    await async_setup_template_platform(
        hass,
        VACUUM_DOMAIN,
        config,
        TemplateStateVacuumEntity,
        TriggerVacuumEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_VACUUMS,
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
        TemplateStateVacuumEntity,
        VACUUM_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_vacuum(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> TemplateStateVacuumEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        TemplateStateVacuumEntity,
        VACUUM_CONFIG_ENTRY_SCHEMA,
    )


def create_issue(
    hass: HomeAssistant, supported_features: int, name: str, entity_id: str
) -> None:
    """Create the battery_level issue."""
    if supported_features & VacuumEntityFeature.BATTERY:
        key = "deprecated_battery_level"
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{key}_{entity_id}",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=key,
            translation_placeholders={
                "entity_name": name,
                "entity_id": entity_id,
            },
        )


class AbstractTemplateVacuum(AbstractTemplateEntity, StateVacuumEntity):
    """Representation of a template vacuum features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""
        self._battery_level_template = config.get(CONF_BATTERY_LEVEL)
        self._fan_speed_template = config.get(CONF_FAN_SPEED)

        self._battery_level = None
        self._attr_fan_speed = None

        # List of valid fan speeds
        self._attr_fan_speed_list = config[CONF_FAN_SPEED_LIST]

        self._attr_supported_features = (
            VacuumEntityFeature.START | VacuumEntityFeature.STATE
        )

        if self._battery_level_template:
            self._attr_supported_features |= VacuumEntityFeature.BATTERY

    def _iterate_scripts(
        self, config: dict[str, Any]
    ) -> Generator[tuple[str, list[dict[str, Any]], VacuumEntityFeature | int]]:
        for action_id, supported_feature in (
            (SERVICE_START, 0),
            (SERVICE_PAUSE, VacuumEntityFeature.PAUSE),
            (SERVICE_STOP, VacuumEntityFeature.STOP),
            (SERVICE_RETURN_TO_BASE, VacuumEntityFeature.RETURN_HOME),
            (SERVICE_CLEAN_SPOT, VacuumEntityFeature.CLEAN_SPOT),
            (SERVICE_LOCATE, VacuumEntityFeature.LOCATE),
            (SERVICE_SET_FAN_SPEED, VacuumEntityFeature.FAN_SPEED),
        ):
            if (action_config := config.get(action_id)) is not None:
                yield (action_id, action_config, supported_feature)

    def _handle_state(self, result: Any) -> None:
        # Validate state
        if result in _VALID_STATES:
            self._attr_activity = result
        elif result == STATE_UNKNOWN:
            self._attr_activity = None
        else:
            _LOGGER.error(
                "Received invalid vacuum state: %s for entity %s. Expected: %s",
                result,
                self.entity_id,
                ", ".join(_VALID_STATES),
            )
            self._attr_activity = None

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.CLEANING
            self.async_write_ha_state()
        await self.async_run_actions(
            self._action_scripts[SERVICE_START], context=self._context
        )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.PAUSED
            self.async_write_ha_state()
        if script := self._action_scripts.get(SERVICE_PAUSE):
            await self.async_run_actions(script, context=self._context)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.IDLE
            self.async_write_ha_state()
        if script := self._action_scripts.get(SERVICE_STOP):
            await self.async_run_actions(script, context=self._context)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.RETURNING
            self.async_write_ha_state()
        if script := self._action_scripts.get(SERVICE_RETURN_TO_BASE):
            await self.async_run_actions(script, context=self._context)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.CLEANING
            self.async_write_ha_state()
        if script := self._action_scripts.get(SERVICE_CLEAN_SPOT):
            await self.async_run_actions(script, context=self._context)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        if script := self._action_scripts.get(SERVICE_LOCATE):
            await self.async_run_actions(script, context=self._context)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if fan_speed not in self._attr_fan_speed_list:
            _LOGGER.error(
                "Received invalid fan speed: %s for entity %s. Expected: %s",
                fan_speed,
                self.entity_id,
                self._attr_fan_speed_list,
            )
            return

        if script := self._action_scripts.get(SERVICE_SET_FAN_SPEED):
            await self.async_run_actions(
                script, run_variables={ATTR_FAN_SPEED: fan_speed}, context=self._context
            )

    @callback
    def _update_battery_level(self, battery_level):
        try:
            battery_level_int = int(battery_level)
            if not 0 <= battery_level_int <= 100:
                raise ValueError  # noqa: TRY301
        except ValueError:
            _LOGGER.error(
                "Received invalid battery level: %s for entity %s. Expected: 0-100",
                battery_level,
                self.entity_id,
            )
            self._attr_battery_level = None
            return

        self._attr_battery_level = battery_level_int

    @callback
    def _update_fan_speed(self, fan_speed):
        if isinstance(fan_speed, TemplateError):
            # This is legacy behavior
            self._attr_fan_speed = None
            self._attr_activity = None
            return

        if fan_speed in self._attr_fan_speed_list:
            self._attr_fan_speed = fan_speed
        elif fan_speed == STATE_UNKNOWN:
            self._attr_fan_speed = None
        else:
            _LOGGER.error(
                "Received invalid fan speed: %s for entity %s. Expected: %s",
                fan_speed,
                self.entity_id,
                self._attr_fan_speed_list,
            )
            self._attr_fan_speed = None


class TemplateStateVacuumEntity(TemplateEntity, AbstractTemplateVacuum):
    """A template vacuum component."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id,
    ) -> None:
        """Initialize the vacuum."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateVacuum.__init__(self, config)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_actions(action_id, action_config, name)
            self._attr_supported_features |= supported_feature

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        create_issue(
            self.hass,
            self._attr_supported_features,
            self._attr_name or DEFAULT_NAME,
            self.entity_id,
        )

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template is not None:
            self.add_template_attribute(
                "_attr_activity", self._template, None, self._update_state
            )
        if self._fan_speed_template is not None:
            self.add_template_attribute(
                "_fan_speed",
                self._fan_speed_template,
                None,
                self._update_fan_speed,
            )
        if self._battery_level_template is not None:
            self.add_template_attribute(
                "_battery_level",
                self._battery_level_template,
                None,
                self._update_battery_level,
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            # This is legacy behavior
            self._attr_activity = None
            if not self._availability_template:
                self._attr_available = True
            return

        self._handle_state(result)


class TriggerVacuumEntity(TriggerEntity, AbstractTemplateVacuum):
    """Vacuum entity based on trigger data."""

    domain = VACUUM_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateVacuum.__init__(self, config)

        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_actions(action_id, action_config, name)
            self._attr_supported_features |= supported_feature

        for key in (CONF_STATE, CONF_FAN_SPEED, CONF_BATTERY_LEVEL):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        create_issue(
            self.hass,
            self._attr_supported_features,
            self._attr_name or DEFAULT_NAME,
            self.entity_id,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, updater in (
            (CONF_STATE, self._handle_state),
            (CONF_FAN_SPEED, self._update_fan_speed),
            (CONF_BATTERY_LEVEL, self._update_battery_level),
        ):
            if (rendered := self._rendered.get(key)) is not None:
                updater(rendered)
                write_ha_state = True

        if len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
