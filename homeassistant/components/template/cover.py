"""Support for covers which integrate with other components."""

from __future__ import annotations

from collections.abc import Generator, Sequence
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as COVER_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity
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

OPEN_STATE = "open"
OPENING_STATE = "opening"
CLOSED_STATE = "closed"
CLOSING_STATE = "closing"

_VALID_STATES = [
    OPEN_STATE,
    OPENING_STATE,
    CLOSED_STATE,
    CLOSING_STATE,
    "true",
    "false",
    "none",
]

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


class AbstractTemplateCover(AbstractTemplateEntity, CoverEntity, RestoreEntity):
    """Representation of a template cover features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True
    _extra_optimistic_options = (CONF_POSITION,)

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(self, config: dict[str, Any]) -> None:  # pylint: disable=super-init-not-called
        """Initialize the features."""

        self._position_template = config.get(CONF_POSITION)
        self._tilt_template = config.get(CONF_TILT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        tilt_optimistic = config.get(CONF_TILT_OPTIMISTIC)
        self._tilt_optimistic = tilt_optimistic or not self._tilt_template
        self._position: int | None = None
        self._is_opening = False
        self._is_closing = False
        self._tilt_value: int | None = None

        # The config requires (open and close scripts) or a set position script,
        # therefore the base supported features will always include them.
        self._attr_supported_features: CoverEntityFeature = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

    def _iterate_scripts(
        self, config: dict[str, Any]
    ) -> Generator[tuple[str, Sequence[dict[str, Any]], CoverEntityFeature | int]]:
        for action_id, supported_feature in (
            (OPEN_ACTION, 0),
            (CLOSE_ACTION, 0),
            (STOP_ACTION, CoverEntityFeature.STOP),
            (POSITION_ACTION, CoverEntityFeature.SET_POSITION),
            (TILT_ACTION, TILT_FEATURES),
        ):
            if (action_config := config.get(action_id)) is not None:
                yield (action_id, action_config, supported_feature)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._position is None:
            return None

        return self._position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is currently opening."""
        return self._is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is currently closing."""
        return self._is_closing

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._position_template or POSITION_ACTION in self._action_scripts:
            return self._position
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._tilt_value

    async def _async_handle_restored_state(self) -> None:
        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_state.state in _VALID_STATES
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and self._position is None
        ):
            if (
                ATTR_CURRENT_POSITION in last_state.attributes
                and (position := last_state.attributes[ATTR_CURRENT_POSITION])
                is not None
            ):
                self._position = position
            elif last_state.state in ("true", OPEN_STATE):
                self._position = 100
            else:
                self._position = 0

            self._is_opening = last_state.state == OPENING_STATE
            self._is_closing = last_state.state == CLOSING_STATE

            if (
                ATTR_CURRENT_TILT_POSITION in last_state.attributes
                and (tilt_position := last_state.attributes[ATTR_CURRENT_TILT_POSITION])
                is not None
            ):
                self._tilt_value = tilt_position

    @callback
    def _update_position(self, result):
        if result is None:
            self._position = None
            return

        try:
            state = float(result)
        except ValueError as err:
            _LOGGER.error(err)
            self._position = None
            return

        if state < 0 or state > 100:
            self._position = None
            _LOGGER.error(
                "Cover position value must be between 0 and 100. Value was: %.2f",
                state,
            )
        else:
            self._position = state

    @callback
    def _update_tilt(self, result):
        if result is None:
            self._tilt_value = None
            return

        try:
            state = float(result)
        except ValueError as err:
            _LOGGER.error(err)
            self._tilt_value = None
            return

        if state < 0 or state > 100:
            self._tilt_value = None
            _LOGGER.error(
                "Tilt value must be between 0 and 100. Value was: %.2f",
                state,
            )
        else:
            self._tilt_value = state

    def _update_opening_and_closing(self, result: Any) -> None:
        state = str(result).lower()

        if state in _VALID_STATES:
            if not self._position_template:
                if state in ("true", OPEN_STATE):
                    self._position = 100
                else:
                    self._position = 0

            self._is_opening = state == OPENING_STATE
            self._is_closing = state == CLOSING_STATE
        else:
            _LOGGER.error(
                "Received invalid cover is_on state: %s for entity %s. Expected: %s",
                state,
                self.entity_id,
                ", ".join(_VALID_STATES),
            )
            if not self._position_template:
                self._position = None

            self._is_opening = False
            self._is_closing = False

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
            self._position = 100
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
            self._position = 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if stop_script := self._action_scripts.get(STOP_ACTION):
            await self.async_run_script(stop_script, context=self._context)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        self._position = kwargs[ATTR_POSITION]
        await self.async_run_script(
            self._action_scripts[POSITION_ACTION],
            run_variables={"position": self._position},
            context=self._context,
        )
        if self._attr_assumed_state:
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        self._tilt_value = 100
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._tilt_value},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        self._tilt_value = 0
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._tilt_value},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        self._tilt_value = kwargs[ATTR_TILT_POSITION]
        await self.async_run_script(
            self._action_scripts[TILT_ACTION],
            run_variables={"tilt": self._tilt_value},
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
        AbstractTemplateCover.__init__(self, config)
        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        await self._async_handle_restored_state()

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        if self._template:
            self.add_template_attribute(
                "_position", self._template, None, self._update_state
            )
        if self._position_template:
            self.add_template_attribute(
                "_position",
                self._position_template,
                None,
                self._update_position,
                none_on_template_error=True,
            )
        if self._tilt_template:
            self.add_template_attribute(
                "_tilt_value",
                self._tilt_template,
                None,
                self._update_tilt,
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._position = None
            return

        self._update_opening_and_closing(result)


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
        AbstractTemplateCover.__init__(self, config)

        # Render the _attr_name before initializing TriggerCoverEntity
        self._attr_name = name = self._rendered.get(CONF_NAME, DEFAULT_NAME)

        for action_id, action_config, supported_feature in self._iterate_scripts(
            config
        ):
            self.add_script(action_id, action_config, name, DOMAIN)
            self._attr_supported_features |= supported_feature

        for key in (CONF_STATE, CONF_POSITION, CONF_TILT):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        await self._async_handle_restored_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, updater in (
            (CONF_STATE, self._update_opening_and_closing),
            (CONF_POSITION, self._update_position),
            (CONF_TILT, self._update_tilt),
        ):
            if (rendered := self._rendered.get(key)) is not None:
                updater(rendered)
                write_ha_state = True

        if not self._attr_assumed_state:
            write_ha_state = True
        elif self._attr_assumed_state and len(self._rendered) > 0:
            # In case any non optimistic template
            write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()
