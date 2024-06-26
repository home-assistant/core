"""Support for covers which integrate with other components."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [
    STATE_OPEN,
    STATE_OPENING,
    STATE_CLOSED,
    STATE_CLOSING,
    "true",
    "false",
    "none",
]

CONF_POSITION_TEMPLATE = "position_template"
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

COVER_SCHEMA = vol.All(
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
            vol.Optional(CONF_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
            vol.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ).extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema),
    cv.has_at_least_one_key(OPEN_ACTION, POSITION_ACTION),
)

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template cover."""
    covers = []

    for object_id, entity_config in config[CONF_COVERS].items():
        entity_config = rewrite_common_legacy_to_modern_conf(entity_config)

        unique_id = entity_config.get(CONF_UNIQUE_ID)

        covers.append(
            CoverTemplate(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return covers


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template cover."""
    async_add_entities(await _async_create_entities(hass, config))


class CoverTemplate(TemplateEntity, CoverEntity):
    """Representation of a Template cover."""

    _attr_should_poll = False

    def __init__(
        self,
        hass,
        object_id,
        config,
        unique_id,
    ):
        """Initialize the Template cover."""
        super().__init__(
            hass, config=config, fallback_name=object_id, unique_id=unique_id
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        friendly_name = self._attr_name
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._position_template = config.get(CONF_POSITION_TEMPLATE)
        self._tilt_template = config.get(CONF_TILT_TEMPLATE)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._open_script = None
        if (open_action := config.get(OPEN_ACTION)) is not None:
            self._open_script = Script(hass, open_action, friendly_name, DOMAIN)
        self._close_script = None
        if (close_action := config.get(CLOSE_ACTION)) is not None:
            self._close_script = Script(hass, close_action, friendly_name, DOMAIN)
        self._stop_script = None
        if (stop_action := config.get(STOP_ACTION)) is not None:
            self._stop_script = Script(hass, stop_action, friendly_name, DOMAIN)
        self._position_script = None
        if (position_action := config.get(POSITION_ACTION)) is not None:
            self._position_script = Script(hass, position_action, friendly_name, DOMAIN)
        self._tilt_script = None
        if (tilt_action := config.get(TILT_ACTION)) is not None:
            self._tilt_script = Script(hass, tilt_action, friendly_name, DOMAIN)
        optimistic = config.get(CONF_OPTIMISTIC)
        self._optimistic = optimistic or (
            optimistic is None and not self._template and not self._position_template
        )
        tilt_optimistic = config.get(CONF_TILT_OPTIMISTIC)
        self._tilt_optimistic = tilt_optimistic or not self._tilt_template
        self._position = None
        self._is_opening = False
        self._is_closing = False
        self._tilt_value = None

        supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        if self._stop_script is not None:
            supported_features |= CoverEntityFeature.STOP
        if self._position_script is not None:
            supported_features |= CoverEntityFeature.SET_POSITION
        if self._tilt_script is not None:
            supported_features |= TILT_FEATURES
        self._attr_supported_features = supported_features

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

        state = str(result).lower()

        if state in _VALID_STATES:
            if not self._position_template:
                if state in ("true", STATE_OPEN):
                    self._position = 100
                else:
                    self._position = 0

            self._is_opening = state == STATE_OPENING
            self._is_closing = state == STATE_CLOSING
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
        if self._position_template or self._position_script:
            return self._position
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._tilt_value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        if self._open_script:
            await self.async_run_script(self._open_script, context=self._context)
        elif self._position_script:
            await self.async_run_script(
                self._position_script,
                run_variables={"position": 100},
                context=self._context,
            )
        if self._optimistic:
            self._position = 100
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        if self._close_script:
            await self.async_run_script(self._close_script, context=self._context)
        elif self._position_script:
            await self.async_run_script(
                self._position_script,
                run_variables={"position": 0},
                context=self._context,
            )
        if self._optimistic:
            self._position = 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        if self._stop_script:
            await self.async_run_script(self._stop_script, context=self._context)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        self._position = kwargs[ATTR_POSITION]
        await self.async_run_script(
            self._position_script,
            run_variables={"position": self._position},
            context=self._context,
        )
        if self._optimistic:
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover open."""
        self._tilt_value = 100
        await self.async_run_script(
            self._tilt_script,
            run_variables={"tilt": self._tilt_value},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the cover closed."""
        self._tilt_value = 0
        await self.async_run_script(
            self._tilt_script,
            run_variables={"tilt": self._tilt_value},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        self._tilt_value = kwargs[ATTR_TILT_POSITION]
        await self.async_run_script(
            self._tilt_script,
            run_variables={"tilt": self._tilt_value},
            context=self._context,
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()
