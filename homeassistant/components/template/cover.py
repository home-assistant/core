"""Support for covers which integrate with other components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as COVER_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COVERS,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
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

OPEN_STATE = "open"
OPENING_STATE = "opening"
CLOSED_STATE = "closed"
CLOSING_STATE = "closing"

CONF_POSITION = "position"
CONF_POSITION_TEMPLATE = "position_template"
CONF_TILT = "tilt"
CONF_TILT_TEMPLATE = "tilt_template"
OPEN_ACTION = "open_cover"
CLOSE_ACTION = "close_cover"
STOP_ACTION = "stop_cover"
POSITION_ACTION = "set_cover_position"
TILT_ACTION = "set_cover_tilt_position"
CONF_TILT_OPTIMISTIC = "tilt_optimistic"

CONF_OPEN_AND_CLOSE = "open_or_close"

TILT_FEATURES = (
    CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
    | CoverEntityFeature.SET_TILT_POSITION
)

LEGACY_FIELDS = {
    CONF_VALUE_TEMPLATE: CONF_STATE,
    CONF_POSITION_TEMPLATE: CONF_POSITION,
    CONF_TILT_TEMPLATE: CONF_TILT,
}

DEFAULT_NAME = "Template Cover"

COVER_COMMON_SCHEMA = vol.Schema(
    {
        vol.Inclusive(CLOSE_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
        vol.Inclusive(OPEN_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_POSITION): cv.template,
        vol.Optional(CONF_STATE): cv.template,
        vol.Optional(CONF_TILT): cv.template,
        vol.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(STOP_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
    }
)

COVER_YAML_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
        }
    )
    .extend(COVER_COMMON_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA)
    .extend(
        make_template_entity_common_modern_schema(COVER_DOMAIN, DEFAULT_NAME).schema
    ),
    cv.has_at_least_one_key(OPEN_ACTION, POSITION_ACTION),
)

COVER_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(CONF_ENTITY_ID),
    vol.Schema(
        {
            vol.Inclusive(OPEN_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
            vol.Inclusive(CLOSE_ACTION, CONF_OPEN_AND_CLOSE): cv.SCRIPT_SCHEMA,
            vol.Optional(STOP_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_POSITION_TEMPLATE): cv.template,
            vol.Optional(CONF_TILT_TEMPLATE): cv.template,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
            vol.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA),
    cv.has_at_least_one_key(OPEN_ACTION, POSITION_ACTION),
)

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_LEGACY_YAML_SCHEMA)}
)

COVER_CONFIG_ENTRY_SCHEMA = vol.All(
    COVER_COMMON_SCHEMA.extend(TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema),
    cv.has_at_least_one_key(OPEN_ACTION, POSITION_ACTION),
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
        LEGACY_FIELDS,
        legacy_key=CONF_COVERS,
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


class AbstractTemplateCover(AbstractTemplateEntity, CoverEntity):
    """Representation of a template cover features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _extra_optimistic_options = (CONF_POSITION,)

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, name: str, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self.setup_state_template(
            CONF_STATE,
            "_attr_current_cover_position",
            template_validators.strenum(
                self, CONF_STATE, CoverState, CoverState.OPEN, CoverState.CLOSED
            ),
            self._update_cover_state,
        )
        self.setup_template(
            CONF_POSITION,
            "_attr_current_cover_position",
            template_validators.number(self, CONF_POSITION, 0, 100),
        )
        self.setup_template(
            CONF_TILT,
            "_attr_current_cover_tilt_position",
            template_validators.number(self, CONF_TILT, 0, 100),
        )
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._tilt_optimistic = (
            config.get(CONF_TILT_OPTIMISTIC) or CONF_TILT not in self._templates
        )

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

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._attr_current_cover_position is None:
            return None

        return self._attr_current_cover_position == 0

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

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if open_script := self._action_scripts.get(OPEN_ACTION):
            await self.async_run_script(open_script, context=self._context)
        elif position_script := self._action_scripts.get(POSITION_ACTION):
            await self.async_run_script(
                position_script,
                run_variables={"position": 100},
                context=self._context,
            )
        if self._attr_assumed_state:
            self._attr_current_cover_position = 100
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if close_script := self._action_scripts.get(CLOSE_ACTION):
            await self.async_run_script(close_script, context=self._context)
        elif position_script := self._action_scripts.get(POSITION_ACTION):
            await self.async_run_script(
                position_script,
                run_variables={"position": 0},
                context=self._context,
            )
        if self._attr_assumed_state:
            self._attr_current_cover_position = 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if stop_script := self._action_scripts.get(STOP_ACTION):
            await self.async_run_script(stop_script, context=self._context)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        self._attr_current_cover_position = kwargs[ATTR_POSITION]
        await self.async_run_script(
            self._action_scripts[POSITION_ACTION],
            run_variables={"position": self._attr_current_cover_position},
            context=self._context,
        )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        self._attr_current_cover_tilt_position = 100
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._attr_current_cover_tilt_position},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        self._attr_current_cover_tilt_position = 0
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._attr_current_cover_tilt_position},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        self._attr_current_cover_tilt_position = kwargs[ATTR_TILT_POSITION]
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._attr_current_cover_tilt_position},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()


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
