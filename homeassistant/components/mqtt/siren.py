"""Support for MQTT sirens."""
from __future__ import annotations

import copy
import functools
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import siren
from homeassistant.components.siren import (
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    TURN_ON_SCHEMA,
    SirenEntity,
    SirenEntityFeature,
    process_turn_on_params,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import JSON_DECODE_EXCEPTIONS, json_dumps, json_loads
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
    CONF_STATE_VALUE_TEMPLATE,
    PAYLOAD_EMPTY_JSON,
    PAYLOAD_NONE,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttCommandTemplate, MqttValueTemplate
from .util import get_mqtt_data

DEFAULT_NAME = "MQTT Siren"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_OPTIMISTIC = False

ENTITY_ID_FORMAT = siren.DOMAIN + ".{}"

CONF_AVAILABLE_TONES = "available_tones"
CONF_COMMAND_OFF_TEMPLATE = "command_off_template"
CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"
CONF_SUPPORT_DURATION = "support_duration"
CONF_SUPPORT_VOLUME_SET = "support_volume_set"

STATE = "state"

PLATFORM_SCHEMA_MODERN = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_AVAILABLE_TONES): cv.ensure_list,
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_OFF_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_OFF): cv.string,
        vol.Optional(CONF_STATE_ON): cv.string,
        vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SUPPORT_DURATION, default=True): cv.boolean,
        vol.Optional(CONF_SUPPORT_VOLUME_SET, default=True): cv.boolean,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Sirens under the siren platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_MODERN.schema),
    warn_for_legacy_schema(siren.DOMAIN),
)

DISCOVERY_SCHEMA = vol.All(PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA))

MQTT_SIREN_ATTRIBUTES_BLOCKED = frozenset(
    {
        ATTR_AVAILABLE_TONES,
        ATTR_DURATION,
        ATTR_TONE,
        ATTR_VOLUME_LEVEL,
    }
)

SUPPORTED_BASE = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

SUPPORTED_ATTRIBUTES = {
    ATTR_DURATION: SirenEntityFeature.DURATION,
    ATTR_TONE: SirenEntityFeature.TONES,
    ATTR_VOLUME_LEVEL: SirenEntityFeature.VOLUME_SET,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT sirens configured under the fan platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        siren.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT siren through configuration.yaml and dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, siren.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry | None = None,
    discovery_data: dict | None = None,
) -> None:
    """Set up the MQTT siren."""
    async_add_entities([MqttSiren(hass, config, config_entry, discovery_data)])


class MqttSiren(MqttEntity, SirenEntity):
    """Representation of a siren that can be controlled using MQTT."""

    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_SIREN_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT siren."""
        self._attr_name = config[CONF_NAME]
        self._attr_should_poll = False
        self._supported_features = SUPPORTED_BASE
        self._attr_is_on = None
        self._state_on = None
        self._state_off = None
        self._optimistic = None

        self._attr_extra_state_attributes: dict[str, Any] = {}

        self.target = None

        super().__init__(hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""

        state_on = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config[CONF_PAYLOAD_ON]

        state_off = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else config[CONF_PAYLOAD_OFF]

        if config[CONF_SUPPORT_DURATION]:
            self._supported_features |= SirenEntityFeature.DURATION
            self._attr_extra_state_attributes[ATTR_DURATION] = None

        if config.get(CONF_AVAILABLE_TONES):
            self._supported_features |= SirenEntityFeature.TONES
            self._attr_available_tones = config[CONF_AVAILABLE_TONES]
            self._attr_extra_state_attributes[ATTR_TONE] = None

        if config[CONF_SUPPORT_VOLUME_SET]:
            self._supported_features |= SirenEntityFeature.VOLUME_SET
            self._attr_extra_state_attributes[ATTR_VOLUME_LEVEL] = None

        self._optimistic = config[CONF_OPTIMISTIC] or CONF_STATE_TOPIC not in config
        self._attr_is_on = False if self._optimistic else None

        command_template = config.get(CONF_COMMAND_TEMPLATE)
        command_off_template = config.get(CONF_COMMAND_OFF_TEMPLATE) or config.get(
            CONF_COMMAND_TEMPLATE
        )
        self._command_templates = {
            CONF_COMMAND_TEMPLATE: MqttCommandTemplate(
                command_template, entity=self
            ).async_render
            if command_template
            else None,
            CONF_COMMAND_OFF_TEMPLATE: MqttCommandTemplate(
                command_off_template, entity=self
            ).async_render
            if command_off_template
            else None,
        }
        self._value_template = MqttValueTemplate(
            config.get(CONF_STATE_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            payload = self._value_template(msg.payload)
            if not payload or payload == PAYLOAD_EMPTY_JSON:
                _LOGGER.debug(
                    "Ignoring empty payload '%s' after rendering for topic %s",
                    payload,
                    msg.topic,
                )
                return
            json_payload = {}
            if payload in [self._state_on, self._state_off, PAYLOAD_NONE]:
                json_payload = {STATE: payload}
            else:
                try:
                    json_payload = json_loads(payload)
                    _LOGGER.debug(
                        "JSON payload detected after processing payload '%s' on topic %s",
                        json_payload,
                        msg.topic,
                    )
                except JSON_DECODE_EXCEPTIONS:
                    _LOGGER.warning(
                        "No valid (JSON) payload detected after processing payload '%s' on topic %s",
                        json_payload,
                        msg.topic,
                    )
                    return
            if STATE in json_payload:
                if json_payload[STATE] == self._state_on:
                    self._attr_is_on = True
                if json_payload[STATE] == self._state_off:
                    self._attr_is_on = False
                if json_payload[STATE] == PAYLOAD_NONE:
                    self._attr_is_on = None
                del json_payload[STATE]

            if json_payload:
                # process attributes
                try:
                    vol.All(TURN_ON_SCHEMA)(json_payload)
                except vol.MultipleInvalid as invalid_siren_parameters:
                    _LOGGER.warning(
                        "Unable to update siren state attributes from payload '%s': %s",
                        json_payload,
                        invalid_siren_parameters,
                    )
                    return
            self._update(process_turn_on_params(self, json_payload))
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    CONF_STATE_TOPIC: {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": state_message_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        mqtt_attributes = super().extra_state_attributes
        attributes = (
            copy.deepcopy(mqtt_attributes) if mqtt_attributes is not None else {}
        )
        attributes.update(self._attr_extra_state_attributes)
        return attributes

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    async def _async_publish(
        self,
        topic: str,
        template: str,
        value: Any,
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Publish MQTT payload with optional command template."""
        template_variables = {STATE: value}
        if variables is not None:
            template_variables.update(variables)
        payload = (
            self._command_templates[template](value, template_variables)
            if self._command_templates[template]
            else json_dumps(template_variables)
        )
        if payload and payload not in PAYLOAD_NONE:
            await self.async_publish(
                self._config[topic],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on.

        This method is a coroutine.
        """
        await self._async_publish(
            CONF_COMMAND_TOPIC,
            CONF_COMMAND_TEMPLATE,
            self._config[CONF_PAYLOAD_ON],
            kwargs,
        )
        if self._optimistic:
            # Optimistically assume that siren has changed state.
            _LOGGER.debug("Writing state attributes %s", kwargs)
            self._attr_is_on = True
            self._update(kwargs)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off.

        This method is a coroutine.
        """
        await self._async_publish(
            CONF_COMMAND_TOPIC,
            CONF_COMMAND_OFF_TEMPLATE,
            self._config[CONF_PAYLOAD_OFF],
        )

        if self._optimistic:
            # Optimistically assume that siren has changed state.
            self._attr_is_on = False
            self.async_write_ha_state()

    def _update(self, data: dict[str, Any]) -> None:
        """Update the extra siren state attributes."""
        for attribute, support in SUPPORTED_ATTRIBUTES.items():
            if self._supported_features & support and attribute in data:
                self._attr_extra_state_attributes[attribute] = data[attribute]
