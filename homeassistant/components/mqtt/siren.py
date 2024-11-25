"""Support for MQTT sirens."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast

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
    SirenTurnOnServiceParameters,
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
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.service_info.mqtt import ReceivePayloadType
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType, VolSchemaType
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads_object

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_STATE_TOPIC,
    CONF_STATE_VALUE_TEMPLATE,
    PAYLOAD_EMPTY_JSON,
    PAYLOAD_NONE,
)
from .entity import MqttEntity, async_setup_entity_entry_helper
from .models import (
    MqttCommandTemplate,
    MqttValueTemplate,
    PublishPayloadType,
    ReceiveMessage,
)
from .schemas import MQTT_ENTITY_COMMON_SCHEMA

PARALLEL_UPDATES = 0

DEFAULT_NAME = "MQTT Siren"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"

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
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_STATE_OFF): cv.string,
        vol.Optional(CONF_STATE_ON): cv.string,
        vol.Optional(CONF_STATE_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SUPPORT_DURATION, default=True): cv.boolean,
        vol.Optional(CONF_SUPPORT_VOLUME_SET, default=True): cv.boolean,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT siren through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttSiren,
        siren.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttSiren(MqttEntity, SirenEntity):
    """Representation of a siren that can be controlled using MQTT."""

    _default_name = DEFAULT_NAME
    _entity_id_format = ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_SIREN_ATTRIBUTES_BLOCKED
    _extra_attributes: dict[str, Any]

    _command_templates: dict[
        str, Callable[[PublishPayloadType, TemplateVarsType], PublishPayloadType] | None
    ]
    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]
    _state_on: str
    _state_off: str
    _optimistic: bool

    @staticmethod
    def config_schema() -> VolSchemaType:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""

        state_on: str | None = config.get(CONF_STATE_ON)
        self._state_on = state_on if state_on else config[CONF_PAYLOAD_ON]

        state_off: str | None = config.get(CONF_STATE_OFF)
        self._state_off = state_off if state_off else config[CONF_PAYLOAD_OFF]

        self._extra_attributes = {}

        _supported_features = SUPPORTED_BASE
        if config[CONF_SUPPORT_DURATION]:
            _supported_features |= SirenEntityFeature.DURATION
            self._extra_attributes[ATTR_DURATION] = None

        if config.get(CONF_AVAILABLE_TONES):
            _supported_features |= SirenEntityFeature.TONES
            self._attr_available_tones = config[CONF_AVAILABLE_TONES]
            self._extra_attributes[ATTR_TONE] = None

        if config[CONF_SUPPORT_VOLUME_SET]:
            _supported_features |= SirenEntityFeature.VOLUME_SET
            self._extra_attributes[ATTR_VOLUME_LEVEL] = None

        self._attr_supported_features = _supported_features
        self._optimistic = config[CONF_OPTIMISTIC] or CONF_STATE_TOPIC not in config
        self._attr_assumed_state = bool(self._optimistic)
        self._attr_is_on = False if self._optimistic else None

        command_template: Template | None = config.get(CONF_COMMAND_TEMPLATE)
        command_off_template: Template | None = (
            config.get(CONF_COMMAND_OFF_TEMPLATE) or command_template
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

    @callback
    def _state_message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT state messages."""
        payload = self._value_template(msg.payload)
        if not payload or payload == PAYLOAD_EMPTY_JSON:
            _LOGGER.debug(
                "Ignoring empty payload '%s' after rendering for topic %s",
                payload,
                msg.topic,
            )
            return
        json_payload: dict[str, Any] = {}
        if payload in [self._state_on, self._state_off, PAYLOAD_NONE]:
            json_payload = {STATE: payload}
        else:
            try:
                json_payload = json_loads_object(payload)
                _LOGGER.debug(
                    (
                        "JSON payload detected after processing payload '%s' on"
                        " topic %s"
                    ),
                    json_payload,
                    msg.topic,
                )
            except JSON_DECODE_EXCEPTIONS:
                _LOGGER.warning(
                    (
                        "No valid (JSON) payload detected after processing payload"
                        " '%s' on topic %s"
                    ),
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
                params: SirenTurnOnServiceParameters
                params = vol.All(TURN_ON_SCHEMA)(json_payload)
            except vol.MultipleInvalid as invalid_siren_parameters:
                _LOGGER.warning(
                    "Unable to update siren state attributes from payload '%s': %s",
                    json_payload,
                    invalid_siren_parameters,
                )
                return
            # To be able to track changes to self._extra_attributes we assign
            # a fresh copy to make the original tracked reference immutable.
            self._extra_attributes = dict(self._extra_attributes)
            self._update(process_turn_on_params(self, params))

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        if not self.add_subscription(
            CONF_STATE_TOPIC,
            self._state_message_received,
            {"_attr_is_on", "_extra_attributes"},
        ):
            # Force into optimistic mode.
            self._optimistic = True
            return

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        extra_attributes = (
            self._attr_extra_state_attributes
            if hasattr(self, "_attr_extra_state_attributes")
            else {}
        )
        if extra_attributes:
            return dict({*self._extra_attributes.items(), *extra_attributes.items()})
        return self._extra_attributes or None

    async def _async_publish(
        self,
        topic: str,
        template: str,
        value: Any,
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Publish MQTT payload with optional command template."""
        template_variables: dict[str, Any] = {STATE: value}
        if variables is not None:
            template_variables.update(variables)
        if command_template := self._command_templates[template]:
            payload = command_template(value, template_variables)
        else:
            payload = json_dumps(template_variables)
        if payload and str(payload) != PAYLOAD_NONE:
            await self.async_publish_with_config(self._config[topic], payload)

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
            self._update(cast(SirenTurnOnServiceParameters, kwargs))
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

    def _update(self, data: SirenTurnOnServiceParameters) -> None:
        """Update the extra siren state attributes."""
        self._extra_attributes.update(
            {
                attribute: data_attr
                for attribute, support in SUPPORTED_ATTRIBUTES.items()
                if self._attr_supported_features & support
                and attribute in data
                and (data_attr := data[attribute])  # type: ignore[literal-required]
                != self._extra_attributes.get(attribute)
            }
        )
