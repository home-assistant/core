"""Support for Becker RF covers."""

import logging

import voluptuous as vol

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.const import (
    CONF_COVERS,
    CONF_NAME,
    CONF_VALUE_TEMPLATE,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CLOSED_POSITION,
    CONF_CHANNEL,
    DEVICE_CLASS,
    DOMAIN,
    INTERMEDIATE_POSITION,
    OPEN_POSITION,
    VENTILATION_POSITION,
)
from .utils import extract_entities, initialise_templates

_LOGGER = logging.getLogger(__name__)

COVER_FEATURES = (
    SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT
)


_VALID_STATES = [STATE_OPEN, STATE_CLOSED, "true", "false"]

COVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_CHANNEL): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Becker Covers based on a config entry."""
    covers = []

    becker_config = hass.data[DOMAIN]
    becker_connector = becker_config["connector"]

    for channel, device_config in becker_config[CONF_COVERS].items():
        name = device_config[CONF_NAME]
        _LOGGER.debug("SETUP cover on channel {channel} with name {name}")

        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        if channel is None:
            _LOGGER.error("Must specify {CONF_CHANNEL}")
            continue
        templates = {
            CONF_VALUE_TEMPLATE: state_template,
        }
        initialise_templates(hass, templates)
        entity_ids = extract_entities(name, "cover", None, templates)
        covers.append(
            BeckerEntity(becker_connector, name, channel, state_template, entity_ids)
        )

    async_add_entities(covers)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the becker platform."""


class BeckerEntity(CoverEntity, RestoreEntity):
    """Representation of a Becker cover device."""

    def __init__(self, becker, name, channel, state_template, entity_ids, position=0):
        """Init the Becker device."""
        self._becker = becker
        self._name = name
        self._channel = channel
        self._template = state_template
        self._entities = entity_ids
        self._position = position
        self._state = True

    async def async_added_to_hass(self):
        """Register callbacks."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_OPEN

    @property
    def name(self):
        """Return the name of the device as reported by tellcore."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the device - the channel."""
        return self._channel

    @property
    def current_cover_position(self):
        """Return current position of cover. None is unknown, 0 is closed, 100 is fully open."""
        return self._position

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS

    @property
    def supported_features(self):
        """Flag supported features."""
        return COVER_FEATURES

    @property
    def is_closed(self):
        """Return true if cover is closed, else False."""
        return self._position == CLOSED_POSITION

    async def async_open_cover(self, **kwargs):
        """Set the cover to the open position."""
        if self._template is None:
            self._position = OPEN_POSITION
        await self._becker.move_up(self._channel)

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        if self._position == CLOSED_POSITION:
            self._position = VENTILATION_POSITION
        elif self._position == VENTILATION_POSITION:
            self._position = OPEN_POSITION
        await self._becker.move_up_intermediate(self._channel)

    async def async_close_cover(self, **kwargs):
        """Set the cover to the closed position."""
        if self._template is None:
            self._position = CLOSED_POSITION
        await self._becker.move_down(self._channel)

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        if self._position == OPEN_POSITION:
            self._position = INTERMEDIATE_POSITION
        elif self._position == INTERMEDIATE_POSITION:
            self._position = CLOSED_POSITION
        await self._becker.move_down_intermediate(self._channel)

    async def async_stop_cover(self, **kwargs):
        """Set the cover to the stopped position."""
        if self._template is None:
            self._position = 50
        await self._becker.stop(self._channel)

    async def async_update(self):
        """Update the position of the cover."""
        if self._template is None:
            return
        try:
            state = self._template.async_render().lower()
            if state in _VALID_STATES:
                if state in ("true", STATE_OPEN):
                    self._position = 100
                else:
                    self._position = 0
            else:
                _LOGGER.error(
                    "Received invalid cover is_on state: %s. Expected: %s",
                    state,
                    ", ".join(_VALID_STATES),
                )
                self._position = None
        except TemplateError as ex:
            _LOGGER.error(ex)
            self._position = None
