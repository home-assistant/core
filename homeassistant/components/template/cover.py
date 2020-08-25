"""Support for covers which integrate with other components."""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

from . import async_setup_reload_service
from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_OPEN, STATE_CLOSED, "true", "false"]

CONF_COVERS = "covers"

CONF_POSITION_TEMPLATE = "position_template"
CONF_TILT_TEMPLATE = "tilt_template"
OPEN_ACTION = "open_cover"
CLOSE_ACTION = "close_cover"
STOP_ACTION = "stop_cover"
POSITION_ACTION = "set_cover_position"
TILT_ACTION = "set_cover_tilt_position"
CONF_TILT_OPTIMISTIC = "tilt_optimistic"

CONF_VALUE_OR_POSITION_TEMPLATE = "value_or_position"
CONF_OPEN_OR_CLOSE = "open_or_close"

TILT_FEATURES = (
    SUPPORT_OPEN_TILT
    | SUPPORT_CLOSE_TILT
    | SUPPORT_STOP_TILT
    | SUPPORT_SET_TILT_POSITION
)

COVER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Inclusive(OPEN_ACTION, CONF_OPEN_OR_CLOSE): cv.SCRIPT_SCHEMA,
            vol.Inclusive(CLOSE_ACTION, CONF_OPEN_OR_CLOSE): cv.SCRIPT_SCHEMA,
            vol.Optional(STOP_ACTION): cv.SCRIPT_SCHEMA,
            vol.Exclusive(
                CONF_POSITION_TEMPLATE, CONF_VALUE_OR_POSITION_TEMPLATE
            ): cv.template,
            vol.Exclusive(
                CONF_VALUE_TEMPLATE, CONF_VALUE_OR_POSITION_TEMPLATE
            ): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Optional(CONF_POSITION_TEMPLATE): cv.template,
            vol.Optional(CONF_TILT_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_TILT_OPTIMISTIC): cv.boolean,
            vol.Optional(POSITION_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(TILT_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
    cv.has_at_least_one_key(OPEN_ACTION, POSITION_ACTION),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_COVERS): cv.schema_with_slug_keys(COVER_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template cover."""
    covers = []

    for device, device_config in config[CONF_COVERS].items():
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        position_template = device_config.get(CONF_POSITION_TEMPLATE)
        tilt_template = device_config.get(CONF_TILT_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)

        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        open_action = device_config.get(OPEN_ACTION)
        close_action = device_config.get(CLOSE_ACTION)
        stop_action = device_config.get(STOP_ACTION)
        position_action = device_config.get(POSITION_ACTION)
        tilt_action = device_config.get(TILT_ACTION)
        optimistic = device_config.get(CONF_OPTIMISTIC)
        tilt_optimistic = device_config.get(CONF_TILT_OPTIMISTIC)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        covers.append(
            CoverTemplate(
                hass,
                device,
                friendly_name,
                device_class,
                state_template,
                position_template,
                tilt_template,
                icon_template,
                entity_picture_template,
                availability_template,
                open_action,
                close_action,
                stop_action,
                position_action,
                tilt_action,
                optimistic,
                tilt_optimistic,
                unique_id,
            )
        )

    return covers


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template cover."""

    await async_setup_reload_service(hass)
    async_add_entities(await _async_create_entities(hass, config))


class CoverTemplate(TemplateEntity, CoverEntity):
    """Representation of a Template cover."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        device_class,
        state_template,
        position_template,
        tilt_template,
        icon_template,
        entity_picture_template,
        availability_template,
        open_action,
        close_action,
        stop_action,
        position_action,
        tilt_action,
        optimistic,
        tilt_optimistic,
        unique_id,
    ):
        """Initialize the Template cover."""
        super().__init__(
            availability_template=availability_template,
            icon_template=icon_template,
            entity_picture_template=entity_picture_template,
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._template = state_template
        self._position_template = position_template
        self._tilt_template = tilt_template
        self._device_class = device_class
        self._open_script = None
        domain = __name__.split(".")[-2]
        if open_action is not None:
            self._open_script = Script(hass, open_action, friendly_name, domain)
        self._close_script = None
        if close_action is not None:
            self._close_script = Script(hass, close_action, friendly_name, domain)
        self._stop_script = None
        if stop_action is not None:
            self._stop_script = Script(hass, stop_action, friendly_name, domain)
        self._position_script = None
        if position_action is not None:
            self._position_script = Script(hass, position_action, friendly_name, domain)
        self._tilt_script = None
        if tilt_action is not None:
            self._tilt_script = Script(hass, tilt_action, friendly_name, domain)
        self._optimistic = optimistic or (not state_template and not position_template)
        self._tilt_optimistic = tilt_optimistic or not tilt_template
        self._position = None
        self._tilt_value = None
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""

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
        await super().async_added_to_hass()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._position = None
            return

        if result in _VALID_STATES:
            if result in ("true", STATE_OPEN):
                self._position = 100
            else:
                self._position = 0
        else:
            _LOGGER.error(
                "Received invalid cover is_on state: %s. Expected: %s",
                result,
                ", ".join(_VALID_STATES),
            )
            self._position = None

    @callback
    def _update_position(self, result):
        try:
            state = float(result)
        except ValueError as err:
            _LOGGER.error(err)
            self._position = None
            return

        if state < 0 or state > 100:
            self._position = None
            _LOGGER.error(
                "Cover position value must be" " between 0 and 100." " Value was: %.2f",
                state,
            )
        else:
            self._position = state

    @callback
    def _update_tilt(self, result):
        try:
            state = float(result)
        except ValueError as err:
            _LOGGER.error(err)
            self._tilt_value = None
            return

        if state < 0 or state > 100:
            self._tilt_value = None
            _LOGGER.error(
                "Tilt value must be between 0 and 100. Value was: %.2f", state,
            )
        else:
            self._tilt_value = state

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this cover."""
        return self._unique_id

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._position == 0

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._position_template or self._position_script:
            return self._position
        return None

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._tilt_value

    @property
    def device_class(self):
        """Return the device class of the cover."""
        return self._device_class

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

        if self._stop_script is not None:
            supported_features |= SUPPORT_STOP

        if self._position_script is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self._tilt_script is not None:
            supported_features |= TILT_FEATURES

        return supported_features

    async def async_open_cover(self, **kwargs):
        """Move the cover up."""
        if self._open_script:
            await self._open_script.async_run(context=self._context)
        elif self._position_script:
            await self._position_script.async_run(
                {"position": 100}, context=self._context
            )
        if self._optimistic:
            self._position = 100
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Move the cover down."""
        if self._close_script:
            await self._close_script.async_run(context=self._context)
        elif self._position_script:
            await self._position_script.async_run(
                {"position": 0}, context=self._context
            )
        if self._optimistic:
            self._position = 0
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        if self._stop_script:
            await self._stop_script.async_run(context=self._context)

    async def async_set_cover_position(self, **kwargs):
        """Set cover position."""
        self._position = kwargs[ATTR_POSITION]
        await self._position_script.async_run(
            {"position": self._position}, context=self._context
        )
        if self._optimistic:
            self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs):
        """Tilt the cover open."""
        self._tilt_value = 100
        await self._tilt_script.async_run(
            {"tilt": self._tilt_value}, context=self._context
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs):
        """Tilt the cover closed."""
        self._tilt_value = 0
        await self._tilt_script.async_run(
            {"tilt": self._tilt_value}, context=self._context
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self._tilt_value = kwargs[ATTR_TILT_POSITION]
        await self._tilt_script.async_run(
            {"tilt": self._tilt_value}, context=self._context
        )
        if self._tilt_optimistic:
            self.async_write_ha_state()
