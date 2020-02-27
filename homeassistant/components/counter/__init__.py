"""Component to count within automations."""
import logging
from typing import Dict, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

ATTR_INITIAL = "initial"
ATTR_STEP = "step"
ATTR_MINIMUM = "minimum"
ATTR_MAXIMUM = "maximum"
VALUE = "value"

CONF_INITIAL = "initial"
CONF_RESTORE = "restore"
CONF_STEP = "step"

DEFAULT_INITIAL = 0
DEFAULT_STEP = 1
DOMAIN = "counter"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SERVICE_DECREMENT = "decrement"
SERVICE_INCREMENT = "increment"
SERVICE_RESET = "reset"
SERVICE_CONFIGURE = "configure"


def _none_to_empty_dict(value):
    if value is None:
        return {}
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                _none_to_empty_dict,
                {
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(
                        CONF_INITIAL, default=DEFAULT_INITIAL
                    ): cv.positive_int,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_MAXIMUM, default=None): vol.Any(
                        None, vol.Coerce(int)
                    ),
                    vol.Optional(CONF_MINIMUM, default=None): vol.Any(
                        None, vol.Coerce(int)
                    ),
                    vol.Optional(CONF_RESTORE, default=True): cv.boolean,
                    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_int,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the counters."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        entities.append(Counter.from_yaml({CONF_ID: object_id, **cfg}))

    if not entities:
        return False

    component.async_register_entity_service(SERVICE_INCREMENT, {}, "async_increment")
    component.async_register_entity_service(SERVICE_DECREMENT, {}, "async_decrement")
    component.async_register_entity_service(SERVICE_RESET, {}, "async_reset")
    component.async_register_entity_service(
        SERVICE_CONFIGURE,
        {
            vol.Optional(ATTR_MINIMUM): vol.Any(None, vol.Coerce(int)),
            vol.Optional(ATTR_MAXIMUM): vol.Any(None, vol.Coerce(int)),
            vol.Optional(ATTR_STEP): cv.positive_int,
            vol.Optional(ATTR_INITIAL): cv.positive_int,
            vol.Optional(VALUE): cv.positive_int,
        },
        "async_configure",
    )

    await component.async_add_entities(entities)
    return True


class Counter(RestoreEntity):
    """Representation of a counter."""

    def __init__(self, config: Dict):
        """Initialize a counter."""
        self._config = config
        self._state = config[CONF_INITIAL]
        self.editable = True

    @classmethod
    def from_yaml(cls, config: Dict):
        """Create counter instance from yaml config."""
        counter = cls(config)
        counter.editable = False
        counter.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        return counter

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the counter."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self):
        """Return the current value of the counter."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        ret = {
            ATTR_EDITABLE: self.editable,
            ATTR_INITIAL: self._config[CONF_INITIAL],
            ATTR_STEP: self._config[CONF_STEP],
        }
        if self._config[CONF_MINIMUM] is not None:
            ret[CONF_MINIMUM] = self._config[CONF_MINIMUM]
        if self._config[CONF_MAXIMUM] is not None:
            ret[CONF_MAXIMUM] = self._config[CONF_MAXIMUM]
        return ret

    @property
    def unique_id(self) -> Optional[str]:
        """Return unique id of the entity."""
        return self._config[CONF_ID]

    def compute_next_state(self, state):
        """Keep the state within the range of min/max values."""
        if self._config[CONF_MINIMUM] is not None:
            state = max(self._config[CONF_MINIMUM], state)
        if self._config[CONF_MAXIMUM] is not None:
            state = min(self._config[CONF_MAXIMUM], state)

        return state

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        # __init__ will set self._state to self._initial, only override
        # if needed.
        if self._config[CONF_RESTORE]:
            state = await self.async_get_last_state()
            if state is not None:
                self._state = self.compute_next_state(int(state.state))
                self._config[CONF_INITIAL] = state.attributes.get(ATTR_INITIAL)
                self._config[CONF_MAXIMUM] = state.attributes.get(ATTR_MAXIMUM)
                self._config[CONF_MINIMUM] = state.attributes.get(ATTR_MINIMUM)
                self._config[CONF_STEP] = state.attributes.get(ATTR_STEP)

    async def async_decrement(self):
        """Decrement the counter."""
        self._state = self.compute_next_state(self._state - self._config[CONF_STEP])
        self.async_write_ha_state()

    async def async_increment(self):
        """Increment a counter."""
        self._state = self.compute_next_state(self._state + self._config[CONF_STEP])
        self.async_write_ha_state()

    async def async_reset(self):
        """Reset a counter."""
        self._state = self.compute_next_state(self._config[CONF_INITIAL])
        self.async_write_ha_state()

    async def async_configure(self, **kwargs):
        """Change the counter's settings with a service."""
        new_state = kwargs.pop(VALUE, self._state)
        self._config = {**self._config, **kwargs}
        self._state = self.compute_next_state(new_state)
        self.async_write_ha_state()
