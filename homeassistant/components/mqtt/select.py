"""Configure select in a device through MQTT topic."""

from __future__ import annotations

from collections.abc import Callable
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
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.typing import ConfigType, VolSchemaType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_OPTIONS,
    CONF_STATE_TOPIC,
)
from .mixins import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Select"

MQTT_SELECT_ATTRIBUTES_BLOCKED = frozenset(
    {
        select.ATTR_OPTIONS,
    }
)


PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Required(CONF_OPTIONS): cv.ensure_list,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT select through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttSelect,
        select.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttSelect(MqttEntity, SelectEntity, RestoreEntity):
    """representation of an MQTT select."""

    _attr_current_option: str | None = None
    _default_name = DEFAULT_NAME
    _entity_id_format = select.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_SELECT_ATTRIBUTES_BLOCKED
    _command_template: Callable[[PublishPayloadType], PublishPayloadType]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]
    _optimistic: bool = False

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._attr_assumed_state = config[CONF_OPTIMISTIC]
        self._attr_options = config[CONF_OPTIONS]

        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE),
            entity=self,
        ).async_render
        self._value_template = MqttValueTemplate(
            config.get(CONF_VALUE_TEMPLATE), entity=self
        ).async_render_with_possible_json_value

    @callback
    def _message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""
        payload = str(self._value_template(msg.payload))
        if not payload.strip():  # No output from template, ignore
            _LOGGER.debug(
                "Ignoring empty payload '%s' after rendering for topic %s",
                payload,
                msg.topic,
            )
            return
        if payload.lower() == "none":
            self._attr_current_option = None
            return

        if payload not in self.options:
            _LOGGER.error(
                "Invalid option for %s: '%s' (valid options: %s)",
                self.entity_id,
                payload,
                self.options,
            )
            return
        self._attr_current_option = payload

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        if not self.add_subscription(
            CONF_STATE_TOPIC, self._message_received, {"_attr_current_option"}
        ):
            # Force into optimistic mode.
            self._attr_assumed_state = True
            return

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

        if self._attr_assumed_state and (
            last_state := await self.async_get_last_state()
        ):
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Update the current value."""
        payload = self._command_template(option)
        if self._attr_assumed_state:
            self._attr_current_option = option
            self.async_write_ha_state()
        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
