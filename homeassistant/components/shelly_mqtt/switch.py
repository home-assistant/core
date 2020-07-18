"""Representation of Shelly MQTT switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import callback

from .const import (
    COMMAND_SUFFIX,
    CONF_MODEL,
    CONF_TOPIC,
    DOMAIN,
    MODEL_SWITCHES,
    MODEL_TITLE,
    MODELS,
)

ON = "on"
OFF = "off"
TOGGLE = "toggle"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Shelly MQTT switch(es) from config entry."""

    device_id = config_entry.data[CONF_DEVICE_ID]
    topic = config_entry.data[CONF_TOPIC]
    model = config_entry.data[CONF_MODEL]
    title = MODELS[model][MODEL_TITLE]
    switches_count = MODELS[model][MODEL_SWITCHES]
    switches = []
    for i in range(switches_count):
        switch_topic = topic + f"relay/{i}"
        if i == 0:
            unique_id = device_id
            via_device = None
        else:
            unique_id = f"{device_id}_{i+1}"
            via_device = device_id
        switches.append(
            ShellyMQTTSwitch(
                hass.components.mqtt, unique_id, switch_topic, title, via_device
            )
        )

    async_add_entities(switches)


class ShellyMQTTSwitch(SwitchEntity):
    """Representation of a Shelly MQTT switch."""

    def __init__(self, mqtt, unique_id, topic, title, via_device):
        """Initialize the MQTT switch."""
        self._mqtt = mqtt
        self._unique_id = unique_id
        self._via_device = via_device
        self._topic = topic
        self._title = title
        self._power = None
        self._energy = None
        self._unsubscribe = None
        self._state = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT events."""
        await super().async_added_to_hass()
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        def state_message_received(msg):
            """Handle new MQTT state messages."""
            if msg.topic == self._topic:
                payload = msg.payload
                if payload == ON:
                    self._state = True
                elif payload == OFF:
                    self._state = False
                # how do we handle the "overpower" state?
            elif msg.topic == self._topic + "/power":

                self._power = float(msg.payload)
            elif msg.topic == self._topic + "/energy":
                # convert from Watt-minute to kWh
                self._energy = float(msg.payload) / 60000

            self.async_write_ha_state()

        self._unsubscribe = await self._mqtt.async_subscribe(
            self._topic + "/#", state_message_received
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._unsubscribe()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        info = {
            "identifiers": {(DOMAIN, self._unique_id)},
            "manufacturer": "Shelly",
            "model": self._title,
            "name": self._unique_id,
        }
        if self._via_device:
            info["via_device"] = (DOMAIN, self._via_device)
        return info

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._unique_id

    @property
    def is_on(self):
        """Return a boolean for the state of the switch."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def current_power_w(self):
        """Return current power usage in W."""
        return self._power

    @property
    def today_energy_kwh(self):
        """Return the total energy usage in kWh."""
        return self._energy

    @property
    def _command_topic(self):
        return f"{self._topic}/{COMMAND_SUFFIX}"

    def _send_command(self, command):
        command_topic = f"{self._topic}/{COMMAND_SUFFIX}"
        self._mqtt.async_publish(command_topic, command)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on.

        This method is a coroutine.
        """
        self._send_command(ON)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off.

        This method is a coroutine.
        """
        self._send_command(OFF)

    async def async_toggle(self, **kwargs):
        """Toggle the switch.

        This method is a coroutine.
        """
        self._send_command(TOGGLE)
