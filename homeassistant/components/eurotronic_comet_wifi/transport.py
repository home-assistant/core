"""MQTT transport for aiocometwifi, backed by Home Assistant's MQTT integration."""

from aiocometwifi import (
    CometWifiConnectionError,
    MqttClient,
    SubscribeCallback,
    SubState,
)

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

KEY_UNSUBSCRIBE = "unsubscribe"


def get_mqtt_client(hass: HomeAssistant) -> MqttClient:
    """Build an aiocometwifi transport that uses Home Assistant's MQTT client.

    MQTT errors (integration not set up, not connected) are raised as
    CometWifiConnectionError.
    """

    async def async_publish(topic: str, payload: str, qos: int, retain: bool) -> None:
        """Publish a message through the Home Assistant MQTT client."""
        try:
            await mqtt.async_publish(hass, topic, payload, qos, retain)
        except HomeAssistantError as err:
            raise CometWifiConnectionError(str(err)) from err

    async def async_subscribe(
        sub_state: SubState | None, topic: str, subscribe_callback: SubscribeCallback
    ) -> SubState:
        """Subscribe to one topic, replacing an existing subscription state."""

        @callback
        def async_message_received(msg: mqtt.ReceiveMessage) -> None:
            """Forward a received message to the library."""
            # Subscribed with the default UTF-8 encoding, so the payload is a str.
            if isinstance(msg.payload, str):
                subscribe_callback(msg.topic, msg.payload)

        if sub_state is not None:
            await async_unsubscribe(sub_state)
        try:
            unsubscribe = await mqtt.async_subscribe(
                hass, topic, async_message_received
            )
        except HomeAssistantError as err:
            raise CometWifiConnectionError(str(err)) from err
        return {KEY_UNSUBSCRIBE: unsubscribe}

    async def async_unsubscribe(sub_state: SubState) -> None:
        """Release a subscription state returned by async_subscribe."""
        sub_state[KEY_UNSUBSCRIBE]()

    return MqttClient(async_publish, async_subscribe, async_unsubscribe)
