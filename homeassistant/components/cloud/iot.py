"""Module to handle messages from Home Assistant cloud."""
import asyncio
import json
import logging
import os

from homeassistant.util.decorator import Registry
from homeassistant.components.alexa import smart_home

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from .const import (
    PUBLISH_TOPIC_FORMAT, SUBSCRIBE_TOPIC_FORMAT,
    IOT_KEEP_ALIVE, ALEXA_PUBLISH_TOPIC)

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)


class CloudIoT:
    """Class to manage the IoT connection."""

    def __init__(self, cloud):
        """Initialize the CloudIoT class."""
        self.cloud = cloud
        self.client = None
        self._remove_hass_stop_listener = None

    @property
    def is_connected(self):
        """Return if we are connected."""
        return self.client is not None

    def connect(self):
        """Connect to the IoT broker."""
        from AWSIoTPythonSDK.exception.operationError import operationError
        from AWSIoTPythonSDK.exception.operationTimeoutException import \
            operationTimeoutException

        assert self.client is None, 'Cloud already connected'

        client = _client_factory(self.cloud)
        hass = self.cloud.hass

        def message_callback(mqtt_client, userdata, msg):
            """Handle IoT message."""
            _, handler, message_id = msg.topic.rsplit('/', 2)

            _LOGGER.debug('Received message on %s: %s', msg.topic, msg.payload)

            self.cloud.hass.add_job(
                async_handle_message, hass, self.cloud, handler,
                message_id, msg.payload.decode('utf-8'))

        try:
            if not client.connect(keepAliveIntervalSecond=IOT_KEEP_ALIVE):
                return

            client.subscribe(
                SUBSCRIBE_TOPIC_FORMAT.format(self.cloud.thing_name), 1,
                message_callback)
            self.client = client
        except (OSError, operationError, operationTimeoutException):
            # SSL Error, connect error, timeout.
            pass

        def _handle_hass_stop(event):
            """Handle Home Assistant shutting down."""
            client.disconnect()

        self._remove_hass_stop_listener = hass.bus.listen_once(
            EVENT_HOMEASSISTANT_STOP, _handle_hass_stop)

    def publish(self, topic, payload):
        """Publish a message to the cloud."""
        topic = PUBLISH_TOPIC_FORMAT.format(self.cloud.thing_name, topic)
        _LOGGER.debug('Publishing message to %s: %s', topic, payload)
        self.client.publish(topic, payload, 1)

    def disconnect(self):
        """Disconnect the client."""
        self.client.disconnect()
        self._remove_hass_stop_listener()
        self.client = None
        self._remove_hass_stop_listener = None


def _client_factory(cloud):
    """Create IoT client."""
    from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
    root_ca = os.path.join(os.path.dirname(__file__), 'aws_iot_root_cert.pem')

    client = AWSIoTMQTTClient(cloud.thing_name)
    client.configureEndpoint(cloud.iot_endpoint, 8883)
    client.configureCredentials(root_ca, cloud.secret_key_path,
                                cloud.certificate_pem_path)

    # Auto back-off reconnects up to 128 seconds. If connected over 20 seconds
    # reset the auto back-off.
    client.configureAutoReconnectBackoffTime(1, 128, 20)

    # Wait 10 seconds for a CONNACK or a disconnect to complete.
    client.configureConnectDisconnectTimeout(10)

    # Set timeout to 5 seconds for publish, subscribe and unsubscribe.
    client.configureMQTTOperationTimeout(5)

    return client


@asyncio.coroutine
def async_handle_message(hass, cloud, handler_name, message_id, payload):
    """Handle incoming IoT message."""
    handler = HANDLERS.get(handler_name)

    if handler is None:
        _LOGGER.warning('Unable to handle message for %s', handler_name)
        return

    yield from handler(hass, cloud, message_id, payload)


@HANDLERS.register('alexa')
@asyncio.coroutine
def async_handle_alexa(hass, cloud, message_id, payload):
    """Handle an incoming IoT message for Alexa."""
    message = json.loads(payload)
    response = yield from smart_home.async_handle_message(hass, message)

    yield from hass.async_add_job(
        cloud.iot.publish, ALEXA_PUBLISH_TOPIC.format(message_id),
        json.dumps(response))
