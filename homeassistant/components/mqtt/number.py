"""Configure number in a device through MQTT topic."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import number
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    NumberEntity,
)
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import (
    CONF_COMMAND_TOPIC,
    CONF_QOS,
    CONF_STATE_TOPIC,
    DOMAIN,
    PLATFORMS,
    subscription,
)
from .. import mqtt
from .const import CONF_RETAIN
from .debug_info import log_messages
from .mixins import MQTT_ENTITY_COMMON_SCHEMA, MqttEntity, async_setup_entry_helper

_LOGGER = logging.getLogger(__name__)

CONF_MIN = "min"
CONF_MAX = "max"
CONF_STEP = "step"

DEFAULT_NAME = "MQTT Number"
DEFAULT_OPTIMISTIC = False

MQTT_NUMBER_ATTRIBUTES_BLOCKED = frozenset(
    {
        number.ATTR_MAX,
        number.ATTR_MIN,
        number.ATTR_STEP,
    }
)


def validate_config(config):
    """Validate that the configuration is valid, throws if it isn't."""
    if config.get(CONF_MIN) >= config.get(CONF_MAX):
        raise vol.Invalid(f"'{CONF_MAX}' must be > '{CONF_MIN}'")

    return config


PLATFORM_SCHEMA = vol.All(
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_MAX, default=DEFAULT_MAX_VALUE): vol.Coerce(float),
            vol.Optional(CONF_MIN, default=DEFAULT_MIN_VALUE): vol.Coerce(float),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Optional(CONF_STEP, default=DEFAULT_STEP): vol.All(
                vol.Coerce(float), vol.Range(min=1e-3)
            ),
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        },
    ).extend(MQTT_ENTITY_COMMON_SCHEMA.schema),
    validate_config,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT number through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT number dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, number.DOMAIN, setup, PLATFORM_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT number."""
    async_add_entities([MqttNumber(hass, config, config_entry, discovery_data)])


class MqttNumber(MqttEntity, NumberEntity, RestoreEntity):
    """representation of an MQTT number."""

    _attributes_extra_blocked = MQTT_NUMBER_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT Number."""
        self._config = config
        self._optimistic = False
        self._sub_state = None

        self._current_number = None

        NumberEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]

        value_template = self._config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = self.hass

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = msg.payload
            value_template = self._config.get(CONF_VALUE_TEMPLATE)
            if value_template is not None:
                payload = value_template.async_render_with_possible_json_value(payload)
            try:
                if payload.isnumeric():
                    num_value = int(payload)
                else:
                    num_value = float(payload)
            except ValueError:
                _LOGGER.warning("Payload '%s' is not a Number", msg.payload)
                return

            if num_value < self.min_value or num_value > self.max_value:
                _LOGGER.error(
                    "Invalid value for %s: %s (range %s - %s)",
                    self.entity_id,
                    num_value,
                    self.min_value,
                    self.max_value,
                )
                return

            self._current_number = num_value
            self.async_write_ha_state()

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = await subscription.async_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": message_received,
                        "qos": self._config[CONF_QOS],
                    }
                },
            )

        if self._optimistic:
            last_state = await self.async_get_last_state()
            if last_state:
                self._current_number = last_state.state

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._config[CONF_MIN]

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._config[CONF_MAX]

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._config[CONF_STEP]

    @property
    def value(self):
        """Return the current value."""
        return self._current_number

    async def async_set_value(self, value: float) -> None:
        """Update the current value."""
        current_number = value

        if value.is_integer():
            current_number = int(value)

        if self._optimistic:
            self._current_number = current_number
            self.async_write_ha_state()

        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            current_number,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic
