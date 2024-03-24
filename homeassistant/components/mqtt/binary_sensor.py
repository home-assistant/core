"""Support for MQTT binary sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_VALUE_TEMPLATE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.event as evt
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import subscription
from .config import MQTT_RO_SCHEMA
from .const import CONF_ENCODING, CONF_QOS, CONF_STATE_TOPIC, PAYLOAD_NONE
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttAvailability,
    MqttEntity,
    async_setup_entity_entry_helper,
    write_state_on_attr_change,
)
from .models import MqttValueTemplate, ReceiveMessage

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Binary sensor"
CONF_OFF_DELAY = "off_delay"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_FORCE_UPDATE = False
CONF_EXPIRE_AFTER = "expire_after"

PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): vol.Any(DEVICE_CLASSES_SCHEMA, None),
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_OFF_DELAY): cv.positive_int,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT binary sensor through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        MqttBinarySensor,
        binary_sensor.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
    )


class MqttBinarySensor(MqttEntity, BinarySensorEntity, RestoreEntity):
    """Representation a binary sensor that is updated by MQTT."""

    _default_name = DEFAULT_NAME
    _delay_listener: CALLBACK_TYPE | None = None
    _entity_id_format = binary_sensor.ENTITY_ID_FORMAT
    _expired: bool | None
    _expire_after: int | None
    _expiration_trigger: CALLBACK_TYPE | None = None

    async def mqtt_async_added_to_hass(self) -> None:
        """Restore state for entities with expire_after set."""
        if (
            self._expire_after
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            # We might have set up a trigger already after subscribing from
            # MqttEntity.async_added_to_hass(), then we should not restore state
            and not self._expiration_trigger
        ):
            expiration_at: datetime = last_state.last_changed + timedelta(
                seconds=self._expire_after
            )
            remain_seconds = (expiration_at - dt_util.utcnow()).total_seconds()

            if remain_seconds <= 0:
                # Skip reactivating the binary_sensor
                _LOGGER.debug("Skip state recovery after reload for %s", self.entity_id)
                return
            self._expired = False
            self._attr_is_on = last_state.state == STATE_ON

            self._expiration_trigger = async_call_later(
                self.hass, remain_seconds, self._value_is_expired
            )
            _LOGGER.debug(
                (
                    "State recovered after reload for %s, remaining time before"
                    " expiring %s"
                ),
                self.entity_id,
                remain_seconds,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Remove exprire triggers."""
        # Clean up expire triggers
        if self._expiration_trigger:
            _LOGGER.debug("Clean up expire after trigger for %s", self.entity_id)
            self._expiration_trigger()
            self._expiration_trigger = None
            self._expired = False
        await MqttEntity.async_will_remove_from_hass(self)

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        self._expire_after = config.get(CONF_EXPIRE_AFTER)
        if self._expire_after:
            self._expired = True
        else:
            self._expired = None
        self._attr_force_update = config[CONF_FORCE_UPDATE]
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

        self._value_template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        def off_delay_listener(now: datetime) -> None:
            """Switch device off after a delay."""
            self._delay_listener = None
            self._attr_is_on = False
            self.async_write_ha_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        @write_state_on_attr_change(self, {"_attr_is_on", "_expired"})
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle a new received MQTT state message."""
            # auto-expire enabled?
            if self._expire_after:
                # When expire_after is set, and we receive a message, assume device is
                # not expired since it has to be to receive the message
                self._expired = False

                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()

                # Set new trigger
                self._expiration_trigger = async_call_later(
                    self.hass, self._expire_after, self._value_is_expired
                )

            payload = self._value_template(msg.payload)
            if not payload.strip():  # No output from template, ignore
                _LOGGER.debug(
                    (
                        "Empty template output for entity: %s with state topic: %s."
                        " Payload: '%s', with value template '%s'"
                    ),
                    self.entity_id,
                    self._config[CONF_STATE_TOPIC],
                    msg.payload,
                    self._config.get(CONF_VALUE_TEMPLATE),
                )
                return

            if payload == self._config[CONF_PAYLOAD_ON]:
                self._attr_is_on = True
            elif payload == self._config[CONF_PAYLOAD_OFF]:
                self._attr_is_on = False
            elif payload == PAYLOAD_NONE:
                self._attr_is_on = None
            else:  # Payload is not for this entity
                template_info = ""
                if self._config.get(CONF_VALUE_TEMPLATE) is not None:
                    template_info = (
                        f", template output: '{str(payload)}', with value template"
                        f" '{str(self._config.get(CONF_VALUE_TEMPLATE))}'"
                    )
                _LOGGER.info(
                    (
                        "No matching payload found for entity: %s with state topic: %s."
                        " Payload: '%s'%s"
                    ),
                    self.entity_id,
                    self._config[CONF_STATE_TOPIC],
                    msg.payload,
                    template_info,
                )
                return

            if self._delay_listener is not None:
                self._delay_listener()
                self._delay_listener = None

            off_delay: int | None = self._config.get(CONF_OFF_DELAY)
            if self._attr_is_on and off_delay is not None:
                self._delay_listener = evt.async_call_later(
                    self.hass, off_delay, off_delay_listener
                )

        self._sub_state = subscription.async_prepare_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_STATE_TOPIC],
                    "msg_callback": state_message_received,
                    "qos": self._config[CONF_QOS],
                    "encoding": self._config[CONF_ENCODING] or None,
                }
            },
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @callback
    def _value_is_expired(self, *_: Any) -> None:
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._expired = True

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true if the device is available and value has not expired."""
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return MqttAvailability.available.fget(self) and (  # type: ignore[attr-defined]
            self._expire_after is None or not self._expired
        )
