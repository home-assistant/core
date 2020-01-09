"""Support to enter a value into a text box."""
import logging
import typing

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_MODE,
    CONF_ICON,
    CONF_ID,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_text"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_INITIAL = "initial"
CONF_MIN = "min"
CONF_MIN_VALUE = 0
CONF_MAX = "max"
CONF_MAX_VALUE = 100
CONF_PATTERN = "pattern"
CONF_VALUE = "value"

MODE_TEXT = "text"
MODE_PASSWORD = "password"

ATTR_VALUE = CONF_VALUE
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_PATTERN = CONF_PATTERN

SERVICE_SET_VALUE = "set_value"


def _cv_input_text(cfg):
    """Configure validation helper for input box (voluptuous)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum > maximum:
        raise vol.Invalid(
            f"Max len ({minimum}) is not greater than min len ({maximum})"
        )
    state = cfg.get(CONF_INITIAL)
    if state is not None and (len(state) < minimum or len(state) > maximum):
        raise vol.Invalid(
            f"Initial value {state} length not in range {minimum}-{maximum}"
        )
    return cfg


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Any(
                vol.All(
                    {
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_MIN, default=CONF_MIN_VALUE): vol.Coerce(int),
                        vol.Optional(CONF_MAX, default=CONF_MAX_VALUE): vol.Coerce(int),
                        vol.Optional(CONF_INITIAL, ""): cv.string,
                        vol.Optional(CONF_ICON): cv.icon,
                        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                        vol.Optional(CONF_PATTERN): cv.string,
                        vol.Optional(CONF_MODE, default=MODE_TEXT): vol.In(
                            [MODE_TEXT, MODE_PASSWORD]
                        ),
                    },
                    _cv_input_text,
                ),
                None,
            )
        )
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass, config):
    """Set up an input text box."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = [
        InputText.from_yaml({CONF_ID: id_, **(cfg or {})})
        for id_, cfg in config[DOMAIN].items()
    ]

    async def reload_service_handler(service_call):
        """Remove all entities and load new ones from config."""
        conf = await component.async_prepare_reload()
        if conf is None:
            return
        new_entities = [
            InputText.from_yaml({CONF_ID: id_, **(cfg or {})})
            for id_, cfg in conf[DOMAIN].items()
        ]
        if new_entities:
            await component.async_add_entities(new_entities)

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(
        SERVICE_SET_VALUE, {vol.Required(ATTR_VALUE): cv.string}, "async_set_value"
    )

    if entities:
        await component.async_add_entities(entities)
    return True


class InputText(RestoreEntity):
    """Represent a text box."""

    def __init__(self, config: typing.Dict):
        """Initialize a text input."""
        self._config = config
        self.editable = True
        self._current_value = config.get(CONF_INITIAL)

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> "InputText":
        """Return entity instance initialized from yaml storage."""
        # set defaults for empty config
        config = {
            CONF_INITIAL: "",
            CONF_MAX: CONF_MAX_VALUE,
            CONF_MIN: CONF_MIN_VALUE,
            CONF_MODE: MODE_TEXT,
            **config,
        }
        input_text = cls(config)
        input_text.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        input_text.editable = False
        return input_text

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the text input entity."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def _maximum(self) -> int:
        """Return max len of the text."""
        return self._config[CONF_MAX]

    @property
    def _minimum(self) -> int:
        """Return min len of the text."""
        return self._config[CONF_MIN]

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._config[CONF_ID]

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_EDITABLE: self.editable,
            ATTR_MIN: self._minimum,
            ATTR_MAX: self._maximum,
            ATTR_PATTERN: self._config.get(CONF_PATTERN),
            ATTR_MODE: self._config[CONF_MODE],
        }

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._current_value is not None:
            return

        state = await self.async_get_last_state()
        value = state and state.state

        # Check against None because value can be 0
        if value is not None and self._minimum <= len(value) <= self._maximum:
            self._current_value = value

    async def async_set_value(self, value):
        """Select new value."""
        if len(value) < self._minimum or len(value) > self._maximum:
            _LOGGER.warning(
                "Invalid value: %s (length range %s - %s)",
                value,
                self._minimum,
                self._maximum,
            )
            return
        self._current_value = value
        await self.async_update_ha_state()
