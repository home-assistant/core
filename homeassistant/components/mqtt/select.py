"""Configure select in a device through MQTT topic."""
import functools
import logging

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
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

CONF_OPTIONS = "options"

DEFAULT_NAME = "MQTT Select"
DEFAULT_OPTIMISTIC = False

MQTT_SELECT_ATTRIBUTES_BLOCKED = frozenset(
    {
        select.ATTR_OPTIONS,
    }
)


def validate_config(config):
    """Validate that the configuration is valid, throws if it isn't."""
    if len(config[CONF_OPTIONS]) < 2:
        raise vol.Invalid(f"'{CONF_OPTIONS}' must include at least 2 options")

    return config


PLATFORM_SCHEMA = vol.All(
    mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
            vol.Required(CONF_OPTIONS): cv.ensure_list,
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        },
    ).extend(MQTT_ENTITY_COMMON_SCHEMA.schema),
    validate_config,
)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Set up MQTT select through configuration.yaml."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    await _async_setup_entity(hass, async_add_entities, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT select dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, select.DOMAIN, setup, PLATFORM_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT select."""
    async_add_entities([MqttSelect(hass, config, config_entry, discovery_data)])


class MqttSelect(MqttEntity, SelectEntity, RestoreEntity):
    """representation of an MQTT select."""

    _attributes_extra_blocked = MQTT_SELECT_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT select."""
        self._config = config
        self._optimistic = False
        self._sub_state = None

        self._attr_current_option = None

        SelectEntity.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return PLATFORM_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]
        self._attr_options = config[CONF_OPTIONS]

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

            if payload not in self.options:
                _LOGGER.error(
                    "Invalid option for %s: '%s' (valid options: %s)",
                    self.entity_id,
                    payload,
                    self.options,
                )
                return

            self._attr_current_option = payload
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
                self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        if self._optimistic:
            self._attr_current_option = option
            self.async_write_ha_state()

        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            option,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic
