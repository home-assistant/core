"""Support for MQTT binary sensors."""
from __future__ import annotations

from datetime import timedelta
import functools
import logging

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
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.event as evt
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import subscription
from .config import MQTT_RO_SCHEMA
from .const import CONF_ENCODING, CONF_QOS, CONF_STATE_TOPIC, PAYLOAD_NONE
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttAvailability,
    MqttEntity,
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttValueTemplate

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MQTT Binary sensor"
CONF_OFF_DELAY = "off_delay"
DEFAULT_PAYLOAD_OFF = "OFF"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_FORCE_UPDATE = False
CONF_EXPIRE_AFTER = "expire_after"

PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_EXPIRE_AFTER): cv.positive_int,
        vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OFF_DELAY): cv.positive_int,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

# Configuring MQTT Binary sensors under the binary_sensor platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(PLATFORM_SCHEMA_MODERN.schema),
    warn_for_legacy_schema(binary_sensor.DOMAIN),
)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT binary sensor configured under the fan platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        binary_sensor.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT binary sensor through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, binary_sensor.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, binary_sensor.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT binary sensor."""
    async_add_entities([MqttBinarySensor(hass, config, config_entry, discovery_data)])


class MqttBinarySensor(MqttEntity, BinarySensorEntity, RestoreEntity):
    """Representation a binary sensor that is updated by MQTT."""

    _entity_id_format = binary_sensor.ENTITY_ID_FORMAT

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT binary sensor."""
        self._state: bool | None = None
        self._expiration_trigger = None
        self._delay_listener = None
        expire_after = config.get(CONF_EXPIRE_AFTER)
        if expire_after is not None and expire_after > 0:
            self._expired = True
        else:
            self._expired = None

        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    async def mqtt_async_added_to_hass(self) -> None:
        """Restore state for entities with expire_after set."""
        if (
            (expire_after := self._config.get(CONF_EXPIRE_AFTER)) is not None
            and expire_after > 0
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            # We might have set up a trigger already after subscribing from
            # MqttEntity.async_added_to_hass(), then we should not restore state
            and not self._expiration_trigger
        ):
            expiration_at = last_state.last_changed + timedelta(seconds=expire_after)
            if expiration_at < (time_now := dt_util.utcnow()):
                # Skip reactivating the binary_sensor
                _LOGGER.debug("Skip state recovery after reload for %s", self.entity_id)
                return
            self._expired = False
            self._state = last_state.state == STATE_ON

            self._expiration_trigger = async_track_point_in_utc_time(
                self.hass, self._value_is_expired, expiration_at
            )
            _LOGGER.debug(
                "State recovered after reload for %s, remaining time before expiring %s",
                self.entity_id,
                expiration_at - time_now,
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
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        self._value_template = MqttValueTemplate(
            self._config.get(CONF_VALUE_TEMPLATE),
            entity=self,
        ).async_render_with_possible_json_value

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        def off_delay_listener(now):
            """Switch device off after a delay."""
            self._delay_listener = None
            self._state = False
            self.async_write_ha_state()

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle a new received MQTT state message."""
            # auto-expire enabled?
            expire_after = self._config.get(CONF_EXPIRE_AFTER)

            if expire_after is not None and expire_after > 0:

                # When expire_after is set, and we receive a message, assume device is
                # not expired since it has to be to receive the message
                self._expired = False

                # Reset old trigger
                if self._expiration_trigger:
                    self._expiration_trigger()

                # Set new trigger
                expiration_at = dt_util.utcnow() + timedelta(seconds=expire_after)

                self._expiration_trigger = async_track_point_in_utc_time(
                    self.hass, self._value_is_expired, expiration_at
                )

            payload = self._value_template(msg.payload)
            if not payload.strip():  # No output from template, ignore
                _LOGGER.debug(
                    "Empty template output for entity: %s with state topic: %s. Payload: '%s', with value template '%s'",
                    self._config[CONF_NAME],
                    self._config[CONF_STATE_TOPIC],
                    msg.payload,
                    self._config.get(CONF_VALUE_TEMPLATE),
                )
                return

            if payload == self._config[CONF_PAYLOAD_ON]:
                self._state = True
            elif payload == self._config[CONF_PAYLOAD_OFF]:
                self._state = False
            elif payload == PAYLOAD_NONE:
                self._state = None
            else:  # Payload is not for this entity
                template_info = ""
                if self._config.get(CONF_VALUE_TEMPLATE) is not None:
                    template_info = f", template output: '{payload}', with value template '{str(self._config.get(CONF_VALUE_TEMPLATE))}'"
                _LOGGER.info(
                    "No matching payload found for entity: %s with state topic: %s. Payload: '%s'%s",
                    self._config[CONF_NAME],
                    self._config[CONF_STATE_TOPIC],
                    msg.payload,
                    template_info,
                )
                return

            if self._delay_listener is not None:
                self._delay_listener()
                self._delay_listener = None

            off_delay = self._config.get(CONF_OFF_DELAY)
            if self._state and off_delay is not None:
                self._delay_listener = evt.async_call_later(
                    self.hass, off_delay, off_delay_listener
                )

            self.async_write_ha_state()

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

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

    @callback
    def _value_is_expired(self, *_):
        """Triggered when value is expired."""
        self._expiration_trigger = None
        self._expired = True

        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def force_update(self):
        """Force update."""
        return self._config[CONF_FORCE_UPDATE]

    @property
    def available(self) -> bool:
        """Return true if the device is available and value has not expired."""
        expire_after = self._config.get(CONF_EXPIRE_AFTER)
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return MqttAvailability.available.fget(self) and (  # type: ignore[attr-defined]
            expire_after is None or not self._expired
        )
