"""Support for covers which integrate with other components."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
import logging
from typing import TYPE_CHECKING, Any, Self, override

import probatio

from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as COVER_DOMAIN,
    ENTITY_ID_FORMAT,
    CoverEntity,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
    CoverServiceArgument,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_STATE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import validators as tcv
from .const import DEFAULT_NAMES, DOMAIN
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

_LOGGER = logging.getLogger(__name__)

OPEN_STATE = "open"
OPENING_STATE = "opening"
CLOSED_STATE = "closed"
CLOSING_STATE = "closing"

CONF_POSITION = "position"
CONF_SUPPORTED_SPEEDS = "supported_speeds"
CONF_TILT = "tilt"
OPEN_ACTION = "open_cover"
CLOSE_ACTION = "close_cover"
STOP_ACTION = "stop_cover"
POSITION_ACTION = "set_cover_position"
TILT_ACTION = "set_cover_tilt_position"
CONF_TILT_OPTIMISTIC = "tilt_optimistic"
CONF_OPEN_TILT_POSITION = "open_tilt_position"
CONF_CLOSED_TILT_POSITIONS = "closed_tilt_positions"
CONF_TILT_START_ANGLE = "tilt_start_angle"
CONF_TILT_END_ANGLE = "tilt_end_angle"
CONF_TILT_ANGLES = "tilt_angles"

CONF_OPEN_AND_CLOSE = "open_or_close"

SCRIPT_FIELDS = (
    CLOSE_ACTION,
    OPEN_ACTION,
    POSITION_ACTION,
    STOP_ACTION,
    TILT_ACTION,
)

TILT_FEATURES = (
    CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)

TILT_CAPABILITY_ATTRIBUTES = {
    CONF_OPEN_TILT_POSITION: "_attr_open_tilt_position",
    CONF_CLOSED_TILT_POSITIONS: "_attr_closed_tilt_positions",
    CONF_TILT_START_ANGLE: "_attr_tilt_start_angle",
    CONF_TILT_END_ANGLE: "_attr_tilt_end_angle",
}

DEFAULT_NAME = DEFAULT_NAMES[Platform.COVER]

COVER_COMMON_SCHEMA = probatio.Schema(
    {
        probatio.Inclusive(CLOSE_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
        probatio.Inclusive(OPEN_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
        probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_POSITION): cv.template,
        probatio.Optional(CONF_STATE): cv.template,
        probatio.Optional(CONF_TILT): cv.template,
        probatio.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(STOP_ACTION): cv.SCRIPT_SCHEMA,
        probatio.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
    }
)

_BLOCKED_ATTRIBUTES = tcv.BlockedTemplateAttributes(
    attributes=(CoverEntityCapabilityAttribute, CoverEntityStateAttribute),
    device_class=True,
)

COVER_YAML_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional(CONF_SUPPORTED_SPEEDS): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
            probatio.Optional(CONF_OPEN_TILT_POSITION): cv.template,
            probatio.Optional(CONF_CLOSED_TILT_POSITIONS): cv.template,
            probatio.Inclusive(CONF_TILT_START_ANGLE, CONF_TILT_ANGLES): cv.template,
            probatio.Inclusive(CONF_TILT_END_ANGLE, CONF_TILT_ANGLES): cv.template,
        }
    )
    .extend(COVER_COMMON_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA)
    .extend(
        make_template_entity_common_schema(
            COVER_DOMAIN, DEFAULT_NAME, _BLOCKED_ATTRIBUTES
        ).schema
    ),
    probatio.AtLeastOne(OPEN_ACTION, POSITION_ACTION),
    *(
        tcv.requires_option(option, TILT_ACTION)
        for option in TILT_CAPABILITY_ATTRIBUTES
    ),
)

COVER_CONFIG_ENTRY_SCHEMA = probatio.All(
    COVER_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema),
    probatio.AtLeastOne(OPEN_ACTION, POSITION_ACTION),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template cover."""
    await async_setup_template_platform(
        hass,
        COVER_DOMAIN,
        config,
        StateCoverEntity,
        TriggerCoverEntity,
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
        StateCoverEntity,
        COVER_CONFIG_ENTRY_SCHEMA,
        True,
        script_options=SCRIPT_FIELDS,
    )


@callback
def async_create_preview_cover(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateCoverEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateCoverEntity,
        COVER_CONFIG_ENTRY_SCHEMA,
        True,
    )


def closed_tilt_positions(
    entity: Entity, attribute: str
) -> Callable[[Any], list[int] | None]:
    """Convert the result to a sorted list of the closed tilt positions 0 and 100."""

    def convert(result: Any) -> list[int] | None:
        if tcv.check_result_for_none(result):
            return None

        if (
            not isinstance(result, list)
            or not result
            or any(
                type(position) is bool or position not in (0, 100)
                for position in result
            )
        ):
            tcv.log_validation_result_error(
                entity, attribute, result, "expected a list of 0, 100 or both"
            )
            return None

        return sorted({int(position) for position in result})

    return convert


def tilt_capability(
    entity: AbstractTemplateCover,
    attribute: str,
    validator: Callable[[Any], Any],
) -> Callable[[Any], None]:
    """Validate a rendered tilt capability, then check it with the others."""

    def update(result: Any) -> None:
        value = None if isinstance(result, TemplateError) else validator(result)
        entity.check_tilt_capabilities(attribute, value)

    return update


@dataclass(kw_only=True)
class CoverExtraStoredData(ExtraStoredData):
    """Holds extra stored data for template cover entities."""

    current_cover_position: int | None
    current_cover_tilt_position: int | None
    is_opening: bool | None
    is_closing: bool | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the cover data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored cover state from a dict."""
        try:
            return cls(
                current_cover_position=restored["current_cover_position"],
                current_cover_tilt_position=restored["current_cover_tilt_position"],
                is_opening=restored["is_opening"],
                is_closing=restored["is_closing"],
            )
        except KeyError:
            return None


class AbstractTemplateCover(AbstractTemplateEntity, CoverEntity, RestoreEntity):
    """Representation of a template cover features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _extra_optimistic_options = (CONF_POSITION,)
    _state_option = CONF_STATE
    _restore_state_extra_data = CoverExtraStoredData
    _restore_state_properties = ("_attr_current_cover_position",)
    _blocked_attributes = _BLOCKED_ATTRIBUTES

    # The super init is not called because TemplateEntity
    # and TriggerEntity will call
    # AbstractTemplateEntity.__init__. This ensures that
    # the __init__ on AbstractTemplateEntity is not
    # called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self.setup_state_template(
            "_attr_current_cover_position",
            tcv.strenum(
                self, CONF_STATE, CoverState, CoverState.OPEN, CoverState.CLOSED
            ),
            self._update_cover_state,
        )
        self.setup_template(
            CONF_POSITION,
            "_attr_current_cover_position",
            tcv.number(self, CONF_POSITION, 0, 100),
        )
        self.setup_template(
            CONF_TILT,
            "_attr_current_cover_tilt_position",
            tcv.number(self, CONF_TILT, 0, 100),
        )
        self.add_assumed_attribute(
            "_attr_current_cover_tilt_position",
            CONF_TILT,
            TILT_ACTION,
            optimistic_option=CONF_TILT_OPTIMISTIC,
        )
        self._rendered_tilt_capabilities: dict[str, Any] = dict.fromkeys(
            TILT_CAPABILITY_ATTRIBUTES
        )
        self._tilt_capabilities_valid = True
        self._tilt_conflict_log_scheduled = False
        for option, validator in (
            (
                CONF_OPEN_TILT_POSITION,
                tcv.number(self, CONF_OPEN_TILT_POSITION, 0, 100, return_type=int),
            ),
            (
                CONF_CLOSED_TILT_POSITIONS,
                closed_tilt_positions(self, CONF_CLOSED_TILT_POSITIONS),
            ),
            (
                CONF_TILT_START_ANGLE,
                tcv.number(self, CONF_TILT_START_ANGLE, -90, 90, return_type=int),
            ),
            (
                CONF_TILT_END_ANGLE,
                tcv.number(self, CONF_TILT_END_ANGLE, -90, 90, return_type=int),
            ),
        ):
            self.setup_template(
                option,
                TILT_CAPABILITY_ATTRIBUTES[option],
                on_update=tilt_capability(self, option, validator),
                none_on_template_error=False,
            )
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_supported_speeds = config.get(CONF_SUPPORTED_SPEEDS) or None

        # The config requires (open and close scripts) or a set position script,
        # therefore the base supported features will always include them.
        self._attr_supported_features: CoverEntityFeature = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        for action_id, supported_feature in (
            (OPEN_ACTION, 0),
            (CLOSE_ACTION, 0),
            (STOP_ACTION, CoverEntityFeature.STOP),
            (POSITION_ACTION, CoverEntityFeature.SET_POSITION),
            (TILT_ACTION, TILT_FEATURES),
        ):
            if (action_config := config.get(action_id)) is not None:
                self.add_script(action_id, action_config, name, DOMAIN)
                self._attr_supported_features |= supported_feature
        if self._attr_supported_speeds:
            self._attr_supported_features |= CoverEntityFeature.SPEED

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._attr_current_cover_position is None:
            return None

        return self._attr_current_cover_position == 0

    @callback
    def check_tilt_capabilities(self, option: str, value: Any) -> None:
        """Store a rendered tilt capability and apply all of them if they agree.

        The base class raises on conflicting tilt capabilities while writing the
        state, so a conflict falls back to the default tilt positions instead.
        """
        if self._rendered_tilt_capabilities[option] == value:
            return
        self._rendered_tilt_capabilities[option] = value
        for rendered_option, attribute in TILT_CAPABILITY_ATTRIBUTES.items():
            setattr(self, attribute, self._rendered_tilt_capabilities[rendered_option])
        try:
            self._tilt_angles()
            self._resolved_closed_tilt_positions()
        except ValueError:
            self._tilt_capabilities_valid = False
            for attribute in TILT_CAPABILITY_ATTRIBUTES.values():
                setattr(self, attribute, None)
            # The options of one render update one at a time, only log a conflict
            # that is still there once all of them are updated
            if not self._tilt_conflict_log_scheduled:
                self._tilt_conflict_log_scheduled = True
                self.hass.loop.call_soon(self._log_tilt_conflict)
        else:
            self._tilt_capabilities_valid = True

    @callback
    def _log_tilt_conflict(self) -> None:
        """Log conflicting tilt capabilities."""
        self._tilt_conflict_log_scheduled = False
        if self._tilt_capabilities_valid:
            return
        _LOGGER.error(
            "Received conflicting tilt options for %s: %s, using the default tilt"
            " positions",
            self.entity_id or self.name,
            ", ".join(
                f"{option}={value}"
                for option, value in self._rendered_tilt_capabilities.items()
            ),
        )

    def _update_cover_state(self, state: CoverState | None) -> None:
        """Update the state of the cover."""
        if state:
            if CONF_POSITION not in self._templates:
                if state == CoverState.OPEN:
                    self._attr_current_cover_position = 100
                else:
                    self._attr_current_cover_position = 0

            self._attr_is_opening = state == CoverState.OPENING
            self._attr_is_closing = state == CoverState.CLOSING
        else:
            if CONF_POSITION not in self._templates:
                self._attr_current_cover_position = None

            self._attr_is_opening = False
            self._attr_is_closing = False

    def _speed_variables(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Return the speed script variable if speeds are configured."""
        # Without speeds, a variable named speed from the config is kept
        if not self._attr_supported_speeds:
            return {}
        return {"speed": kwargs.get(CoverServiceArgument.SPEED)}

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        speed_variables = self._speed_variables(kwargs)
        if open_script := self._action_scripts.get(OPEN_ACTION):
            await self.async_run_script(
                open_script, run_variables=speed_variables, context=self._context
            )
        elif position_script := self._action_scripts.get(POSITION_ACTION):
            await self.async_run_script(
                position_script,
                run_variables={"position": 100, **speed_variables},
                context=self._context,
            )
        if self._attr_assumed_state:
            self._attr_current_cover_position = 100
            self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        speed_variables = self._speed_variables(kwargs)
        if close_script := self._action_scripts.get(CLOSE_ACTION):
            await self.async_run_script(
                close_script, run_variables=speed_variables, context=self._context
            )
        elif position_script := self._action_scripts.get(POSITION_ACTION):
            await self.async_run_script(
                position_script,
                run_variables={"position": 0, **speed_variables},
                context=self._context,
            )
        if self._attr_assumed_state:
            self._attr_current_cover_position = 0
            self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if stop_script := self._action_scripts.get(STOP_ACTION):
            await self.async_run_script(stop_script, context=self._context)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        position = kwargs[CoverServiceArgument.POSITION]
        await self.async_run_script(
            self._action_scripts[POSITION_ACTION],
            run_variables={"position": position, **self._speed_variables(kwargs)},
            context=self._context,
        )
        if self._attr_assumed_state:
            self._attr_current_cover_position = position
            self.async_write_ha_state()

    async def _set_tilt_position(self, position: int) -> None:
        if script := self._action_scripts.get(TILT_ACTION):
            await self.async_run_script(
                script, run_variables={"tilt": position}, context=self._context
            )
        self.write_assumed_attribute(CONF_TILT, position)

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        await self._set_tilt_position(self._resolved_open_tilt_position())

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        closed_positions = self._resolved_closed_tilt_positions()
        position = closed_positions[0]
        if (
            len(closed_positions) > 1
            and (tilt := self.current_cover_tilt_position) is not None
        ):
            # Close at the end on the current side, without turning through open
            position = 100 if tilt > self._resolved_open_tilt_position() else 0
        await self._set_tilt_position(position)

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        await self._set_tilt_position(kwargs[CoverServiceArgument.TILT_POSITION])

    @property
    @override
    def extra_restore_state_data(self) -> CoverExtraStoredData:
        """Return cover specific state data to be restored."""
        return CoverExtraStoredData(
            current_cover_position=self._attr_current_cover_position,
            current_cover_tilt_position=self._attr_current_cover_tilt_position,
            is_opening=self._attr_is_opening,
            is_closing=self._attr_is_closing,
        )

    @override
    def restore_extra_data(self, extra_data: CoverExtraStoredData) -> None:
        """Restore the extra data."""
        self._attr_current_cover_position = extra_data.current_cover_position
        self._attr_current_cover_tilt_position = extra_data.current_cover_tilt_position
        self._attr_is_opening = extra_data.is_opening
        self._attr_is_closing = extra_data.is_closing


class StateCoverEntity(TemplateEntity, AbstractTemplateCover):
    """Representation of a Template cover."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id,
    ) -> None:
        """Initialize the Template cover."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        AbstractTemplateCover.__init__(self, name, config)


class TriggerCoverEntity(TriggerEntity, AbstractTemplateCover):
    """Cover entity based on trigger data."""

    domain = COVER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        # Render the _attr_name before initializing TriggerCoverEntity
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)
        AbstractTemplateCover.__init__(self, name, config)
