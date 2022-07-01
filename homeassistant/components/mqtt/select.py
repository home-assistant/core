"""Configure select in a device through MQTT topic."""
from __future__ import annotations

import functools
import logging

import voluptuous as vol

from homeassistant.components import select
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttCommandTemplate, MqttValueTemplate

_LOGGER = logging.getLogger(__name__)

CONF_OPTIONS = "options"

DEFAULT_NAME = "MQTT Select"
DEFAULT_OPTIMISTIC = False

MQTT_SELECT_ATTRIBUTES_BLOCKED = frozenset(
    {
        select.ATTR_OPTIONS,
    }
)


PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Required(CONF_OPTIONS): cv.ensure_list,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Select under the select platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_MODERN.schema),
    warn_for_legacy_schema(select.DOMAIN),
)

DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT select configured under the select platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        select.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT select through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, select.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, select.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT select."""
    async_add_entities([MqttSelect(hass, config, config_entry, discovery_data)])


class MqttSelect(MqttEntity, SelectEntity, RestoreEntity):
    """representation of an MQTT select."""

    _entity_id_format = select.ENTITY_ID_FORMAT

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
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]
        self._attr_options = config[CONF_OPTIONS]

        self._templates = {
            CONF_COMMAND_TEMPLATE: MqttCommandTemplate(
                config.get(CONF_COMMAND_TEMPLATE), entity=self
            ).async_render,
            CONF_VALUE_TEMPLATE: MqttValueTemplate(
                config.get(CONF_VALUE_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
        }

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = self._templates[CONF_VALUE_TEMPLATE](msg.payload)

            if payload.lower() == "none":
                payload = None

            if payload is not None and payload not in self.options:
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
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": message_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

        if self._optimistic and (last_state := await self.async_get_last_state()):
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        payload = self._templates[CONF_COMMAND_TEMPLATE](option)
        if self._optimistic:
            self._attr_current_option = option
            self.async_write_ha_state()

        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic
