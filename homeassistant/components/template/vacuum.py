"""Support for Template vacuums."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Self, override

import probatio

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityCapabilityAttribute,
    VacuumEntityFeature,
    VacuumEntityStateAttribute,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_STATE, CONF_UNIQUE_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import validators as tcv
from .const import DEFAULT_NAMES, DOMAIN, VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS
from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .repairs import format_deprecated_options
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

CONF_CLEAN_SEGMENTS = "clean_segments"
CONF_FAN_SPEED = "fan_speed"
CONF_FAN_SPEED_LIST = "fan_speeds"
CONF_SEGMENTS = "segments"
CONF_VACUUMS = "vacuums"

CONF_CLEAN_SPOT_ACTION = "clean_spot"
CONF_LOCATE_ACTION = "locate"
CONF_PAUSE_ACTION = "pause"
CONF_RETURN_TO_BASE_ACTION = "return_to_base"
CONF_SET_FAN_SPEED_ACTION = "set_fan_speed"
CONF_START_ACTION = "start"
CONF_STOP_ACTION = "stop"

DEFAULT_NAME = DEFAULT_NAMES[Platform.VACUUM]

ENTITY_ID_FORMAT = VACUUM_DOMAIN + ".{}"

SCRIPT_FIELDS = (
    CONF_CLEAN_SEGMENTS,
    CONF_CLEAN_SPOT_ACTION,
    CONF_LOCATE_ACTION,
    CONF_PAUSE_ACTION,
    CONF_RETURN_TO_BASE_ACTION,
    CONF_SET_FAN_SPEED_ACTION,
    CONF_START_ACTION,
    CONF_STOP_ACTION,
)

CLEAN_AREA_GROUP = "clean_area_group"

DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID = (
    "deprecated_vacuum_helper_incomplete_fan_speed_options"
)

VACUUM_COMMON_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_FAN_SPEED_LIST): probatio.EnsureList(),
        probatio.Optional(CONF_FAN_SPEED): cv.template,
        probatio.Optional(CONF_STATE): cv.template,
        probatio.Inclusive(
            CONF_SEGMENTS,
            CLEAN_AREA_GROUP,
            f"Options `{CONF_SEGMENTS}` and `{CONF_CLEAN_SEGMENTS}` must both exist",
        ): cv.template,
        probatio.Optional(CONF_CLEAN_SPOT_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_LOCATE_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_PAUSE_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_RETURN_TO_BASE_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_SET_FAN_SPEED_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Required(CONF_START_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_STOP_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(
            CONF_CLEAN_SEGMENTS,
            CLEAN_AREA_GROUP,
            f"Options `{CONF_SEGMENTS}` and `{CONF_CLEAN_SEGMENTS}` must both exist",
        ): cv.SCRIPT_SCHEMA,
    }
)

_BLOCKED_ATTRIBUTES = tcv.BlockedTemplateAttributes(
    attributes=(VacuumEntityCapabilityAttribute, VacuumEntityStateAttribute)
)

VACUUM_YAML_SCHEMA = probatio.All(
    VACUUM_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA).extend(
        make_template_entity_common_schema(VACUUM_DOMAIN, DEFAULT_NAME).schema
    ),
    cv.key_dependency(CONF_SEGMENTS, CONF_UNIQUE_ID),
    cv.key_dependency(CONF_CLEAN_SEGMENTS, CONF_UNIQUE_ID),
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
        script_options=SCRIPT_FIELDS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    issue_id = (
        f"{DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID}_{config_entry.entry_id}"
    )
    if incomplete := VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.deprecated_options(
        config_entry.options
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version=VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.breaks_in_ha_version,
            config_entry_id=config_entry.entry_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID,
            translation_placeholders={
                "name": config_entry.title,
                "breaks_in_ha_version": (
                    VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.breaks_in_ha_version
                ),
                "options": format_deprecated_options(
                    hass, VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS, incomplete, {}
                ),
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)

    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        TemplateStateVacuumEntity,
        VACUUM_CONFIG_ENTRY_SCHEMA,
        script_options=SCRIPT_FIELDS,
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


def validate_segments(
    entity: AbstractTemplateVacuum,
    option: str,
) -> Callable[[Any], list[Segment] | None]:
    """Parse segment template to list of segments."""

    def parse(result: Any) -> list[Segment] | None:
        if tcv.check_result_for_none(result):
            return None

        segments: list[Segment] = []

        if not isinstance(result, list):
            tcv.log_validation_result_error(
                entity,
                option,
                result,
                "expected a list of dictionaries",
            )
            return None

        for item in result:
            if not isinstance(item, dict):
                tcv.log_validation_result_error(
                    entity,
                    option,
                    item,
                    "expected dictionary with keys id, name and optional group"
                    " and string values",
                )
                return None

            if (
                not isinstance(item.get("id"), str)
                or not isinstance(item.get("name"), str)
                or ("group" in item and not isinstance(item["group"], str))
                or not set(item).issubset({"id", "name", "group"})
            ):
                tcv.log_validation_result_error(
                    entity,
                    option,
                    item,
                    "expected dictionary with keys id, name and optional group"
                    " and string values",
                )
                return None

            segments.append(Segment(**item))
        return segments

    return parse


@dataclass(kw_only=True)
class VacuumExtraStoredData(ExtraStoredData):
    """Holds extra stored data for template vacuum entities."""

    activity: VacuumActivity | None
    fan_speed: str | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the vacuum data."""
        return {
            "activity": self.activity.value if self.activity else None,
            "fan_speed": self.fan_speed,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored vacuum state from a dict."""
        try:
            activity: VacuumActivity | None = None
            if _activity := restored["activity"]:
                activity = VacuumActivity(_activity)

            return cls(
                activity=activity,
                fan_speed=restored["fan_speed"],
            )
        except KeyError, ValueError:
            return None


class AbstractTemplateVacuum(AbstractTemplateEntity, StateVacuumEntity, RestoreEntity):
    """Representation of a template vacuum features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _state_option = CONF_STATE
    _restore_state_extra_data = VacuumExtraStoredData
    _restore_state_properties = ("_attr_activity",)
    _blocked_attributes = _BLOCKED_ATTRIBUTES

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        # List of valid fan speeds
        self._attr_fan_speed_list = config.get(CONF_FAN_SPEED_LIST, [])
        self._segments: list[Segment] = []
        self.setup_state_template(
            "_attr_activity",
            tcv.strenum(self, CONF_STATE, VacuumActivity),
        )
        self.setup_template(
            CONF_FAN_SPEED,
            "_attr_fan_speed",
            tcv.item_in_list(self, CONF_FAN_SPEED, self._attr_fan_speed_list),
        )
        self.add_assumed_attribute(
            "_attr_fan_speed", CONF_FAN_SPEED, CONF_SET_FAN_SPEED_ACTION
        )

        self.setup_template(
            CONF_SEGMENTS,
            "_segments",
            validate_segments(self, CONF_SEGMENTS),
            self._update_segments,
        )

        self._attr_supported_features = (
            VacuumEntityFeature.START | VacuumEntityFeature.STATE
        )

        for action_id, supported_feature in (
            (CONF_START_ACTION, 0),
            (CONF_PAUSE_ACTION, VacuumEntityFeature.PAUSE),
            (CONF_STOP_ACTION, VacuumEntityFeature.STOP),
            (CONF_RETURN_TO_BASE_ACTION, VacuumEntityFeature.RETURN_HOME),
            (CONF_CLEAN_SPOT_ACTION, VacuumEntityFeature.CLEAN_SPOT),
            (CONF_LOCATE_ACTION, VacuumEntityFeature.LOCATE),
            (CONF_SET_FAN_SPEED_ACTION, VacuumEntityFeature.FAN_SPEED),
            (CONF_CLEAN_SEGMENTS, VacuumEntityFeature.CLEAN_AREA),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature

    @callback
    def _update_segments(self, result: list[Segment] | None) -> None:
        """Save segment templates and create issue when segments changed."""
        if result is None:
            return

        self._segments = result

        if (last_seen := self.last_seen_segments) is not None and {
            s.id: s for s in last_seen
        } != {s.id: s for s in self._segments}:
            self.async_create_segments_issue()

    @override
    async def async_get_segments(self) -> list[Segment]:
        """Return the available segments."""
        return self._segments

    @override
    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.CLEANING
            self.async_write_ha_state()
        if script := self._action_scripts.get(CONF_CLEAN_SEGMENTS):
            await self.async_run_script(
                script,
                run_variables={"segment_ids": segment_ids},
                context=self._context,
            )

    @override
    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.CLEANING
            self.async_write_ha_state()
        await self.async_run_script(
            self._action_scripts[CONF_START_ACTION], context=self._context
        )

    @override
    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.PAUSED
            self.async_write_ha_state()
        if script := self._action_scripts.get(CONF_PAUSE_ACTION):
            await self.async_run_script(script, context=self._context)

    @override
    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.IDLE
            self.async_write_ha_state()
        if script := self._action_scripts.get(CONF_STOP_ACTION):
            await self.async_run_script(script, context=self._context)

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.RETURNING
            self.async_write_ha_state()
        if script := self._action_scripts.get(CONF_RETURN_TO_BASE_ACTION):
            await self.async_run_script(script, context=self._context)

    @override
    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        if self._attr_assumed_state:
            self._attr_activity = VacuumActivity.CLEANING
            self.async_write_ha_state()
        if script := self._action_scripts.get(CONF_CLEAN_SPOT_ACTION):
            await self.async_run_script(script, context=self._context)

    @override
    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        if script := self._action_scripts.get(CONF_LOCATE_ACTION):
            await self.async_run_script(script, context=self._context)

    @override
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

        if script := self._action_scripts.get(CONF_SET_FAN_SPEED_ACTION):
            await self.async_run_script(
                script, run_variables={"fan_speed": fan_speed}, context=self._context
            )

        self.write_assumed_attribute(CONF_FAN_SPEED, fan_speed)

    @property
    @override
    def extra_restore_state_data(self) -> VacuumExtraStoredData:
        """Return vacuum specific state data to be restored."""
        return VacuumExtraStoredData(
            activity=self._attr_activity,
            fan_speed=self._attr_fan_speed,
        )

    @override
    def restore_extra_data(self, extra_data: VacuumExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_activity = extra_data.activity
        self._attr_fan_speed = extra_data.fan_speed


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
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None
        AbstractTemplateVacuum.__init__(self, name, config)


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
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateVacuum.__init__(self, name, config)
