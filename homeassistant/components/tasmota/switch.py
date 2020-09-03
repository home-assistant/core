"""Support for Tasmota switches."""
import logging

from hatasmota.const import (
    CONF_COMMAND_TOPIC,
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_POWER,
    CONF_STATE_POWER_OFF,
    CONF_STATE_POWER_ON,
    CONF_STATE_TOPIC,
    CONF_UNIQUE_ID,
)
from hatasmota.utils import get_state_power

from homeassistant.components import mqtt, switch
from homeassistant.components.mqtt import subscription
from homeassistant.components.mqtt.debug_info import log_messages
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW, clear_discovery_hash
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota switch dynamically through discovery."""

    async def async_discover(config, discovery_hash, discovery_payload):
        """Discover and add a Tasmota switch."""
        discovery_data = discovery_payload.discovery_data
        try:
            await _async_setup_entity(
                config, discovery_hash, async_add_entities, config_entry, discovery_data
            )
        except Exception:
            clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(switch.DOMAIN, TASMOTA_DOMAIN),
        async_discover,
    )


async def _async_setup_entity(
    config, discovery_hash, async_add_entities, config_entry, discovery_data
):
    """Set up the Tasmota switch."""
    async_add_entities(
        [TasmotaSwitch(config, discovery_hash, config_entry, discovery_data)]
    )


class TasmotaSwitch(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    SwitchEntity,
    RestoreEntity,
):
    """Representation of a Tasmota switch."""

    def __init__(self, config, discovery_hash, config_entry, discovery_data):
        """Initialize the Tasmota switch."""
        self._state = False
        self._sub_state = None

        self._unique_id = config[CONF_UNIQUE_ID]

        # Process config
        self._setup_from_config(config)

        TasmotaAvailability.__init__(self, config)
        TasmotaDiscoveryUpdate.__init__(
            self, config, discovery_hash, self.discovery_update
        )

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def discovery_update(self, config):
        """Handle updated discovery message."""
        self._setup_from_config(config)
        await self.availability_discovery_update(config)
        await self._subscribe_topics()
        self.async_write_ha_state()

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._config = config

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            state = get_state_power(msg.payload, self._config[CONF_STATE_POWER])
            if state == self._config[CONF_STATE_POWER_ON]:
                self._state = True
            elif state == self._config[CONF_STATE_POWER_OFF]:
                self._state = False

            self.async_write_ha_state()

        self._sub_state = await subscription.async_subscribe_topics(
            self.hass,
            self._sub_state,
            {
                "state_topic": {
                    "topic": self._config[CONF_STATE_TOPIC],
                    "msg_callback": state_message_received,
                    "qos": self._config[CONF_QOS],
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._sub_state = await subscription.async_unsubscribe_topics(
            self.hass, self._sub_state
        )
        await TasmotaAvailability.async_will_remove_from_hass(self)
        await TasmotaDiscoveryUpdate.async_will_remove_from_hass(self)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._config[CONF_NAME]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon."""
        return None

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {"identifiers": {(TASMOTA_DOMAIN, self._config[CONF_DEVICE_ID])}}

    async def async_turn_on(self, **kwargs):
        """Turn the device on.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_STATE_POWER_ON],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )

    async def async_turn_off(self, **kwargs):
        """Turn the device off.

        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass,
            self._config[CONF_COMMAND_TOPIC],
            self._config[CONF_STATE_POWER_OFF],
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
        )
