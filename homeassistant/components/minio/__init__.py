"""Minio component."""

import logging
import os
import threading
from queue import Queue
from typing import List

import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_START, \
    EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'minio'
CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_ACCESS_KEY = 'access_key'
CONF_SECRET_KEY = 'secret_key'
CONF_SECURE = 'secure'
CONF_LISTEN = 'listen'
CONF_LISTEN_BUCKET = 'bucket'
CONF_LISTEN_PREFIX = 'prefix'
CONF_LISTEN_SUFFIX = 'suffix'
CONF_LISTEN_EVENTS = 'events'

CONF_LISTEN_PREFIX_DEFAULT = ''
CONF_LISTEN_SUFFIX_DEFAULT = '.*'
CONF_LISTEN_EVENTS_DEFAULT = 's3:ObjectCreated:*'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_ACCESS_KEY): cv.string,
        vol.Required(CONF_SECRET_KEY): cv.string,
        vol.Required(CONF_SECURE): cv.boolean,
        vol.Optional(CONF_LISTEN): vol.All(cv.ensure_list, [vol.Schema({
            vol.Required(CONF_LISTEN_BUCKET): cv.string,
            vol.Optional(
                CONF_LISTEN_PREFIX,
                default=CONF_LISTEN_PREFIX_DEFAULT
            ): cv.string,
            vol.Optional(
                CONF_LISTEN_SUFFIX,
                default=CONF_LISTEN_SUFFIX_DEFAULT
            ): cv.string,
            vol.Optional(
                CONF_LISTEN_EVENTS,
                default=CONF_LISTEN_EVENTS_DEFAULT
            ): cv.string,
        })])
    })
}, extra=vol.ALLOW_EXTRA)

BUCKET_KEY_SCHEMA = vol.Schema({
    vol.Required('bucket'): cv.template,
    vol.Required('key'): cv.template,
})

BUCKET_KEY_FILE_SCHEMA = BUCKET_KEY_SCHEMA.extend({
    vol.Required('file_path'): cv.template,
})


def get_minio_endpoint(host: str, port: int) -> str:
    """Create minio endpoint from host and port."""
    return host + ':' + str(port)


class QueueListener(threading.Thread):
    """Forward events from queue into HASS event bus."""

    def __init__(self, hass):
        """Create queue."""
        super().__init__()
        self.__hass = hass
        self.__q = Queue()

    def run(self):
        """Listen to queue events, and forward them to HASS event bus."""
        _LOGGER.info('Running QueueListener')
        while True:
            event = self.__q.get()
            if event is None:
                break

            _, file_name = os.path.split(event['key'])

            _LOGGER.debug(
                'Sending event %s, %s, %s',
                event['event_name'],
                event['bucket'],
                event['key']
            )
            self.__hass.bus.fire(DOMAIN, {
                'file_name': file_name,
                **event,
            })

    @property
    def queue(self):
        """Return wrapped queue."""
        return self.__q

    def stop(self):
        """Stop run by putting None into queue and join the thread."""
        _LOGGER.info('Stopping QueueListener')
        self.__q.put(None)
        self.join()
        _LOGGER.info('Stopped QueueListener')

    def start_handler(self, _):
        """Start handler helper method."""
        self.start()

    def stop_handler(self, _):
        """Stop handler helper method."""
        self.stop()


class MinioListener:
    """MinioEventThread wrapper with helper methods."""

    def __init__(
            self,
            queue: Queue,
            endpoint: str,
            access_key: str,
            secret_key: str,
            secure: bool,
            bucket_name: str,
            prefix: str,
            suffix: str,
            events: List[str]
    ):
        """Create Listener."""
        self.__queue = queue
        self.__endpoint = endpoint
        self.__access_key = access_key
        self.__secret_key = secret_key
        self.__secure = secure
        self.__bucket_name = bucket_name
        self.__prefix = prefix
        self.__suffix = suffix
        self.__events = events
        self.__minio_event_thread = None

    def start_handler(self, _):
        """Create and start the event thread."""
        from .minio_helper import MinioEventThread

        self.__minio_event_thread = MinioEventThread(
            self.__queue,
            self.__endpoint,
            self.__access_key,
            self.__secret_key,
            self.__secure,
            self.__bucket_name,
            self.__prefix,
            self.__suffix,
            self.__events
        )
        self.__minio_event_thread.start()

    def stop_handler(self, _):
        """Issue stop and wait for thread to join."""
        if self.__minio_event_thread is not None:
            self.__minio_event_thread.stop()


def setup(hass, config):
    """Set up MinioClient and event listeners."""
    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    access_key = conf[CONF_ACCESS_KEY]
    secret_key = conf[CONF_SECRET_KEY]
    secure = conf[CONF_SECURE]

    queue_listener = QueueListener(hass)
    queue = queue_listener.queue

    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_START,
        queue_listener.start_handler
    )
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP,
        queue_listener.stop_handler
    )

    def _setup_listener(listener_conf):
        bucket = listener_conf[CONF_LISTEN_BUCKET]
        prefix = listener_conf[CONF_LISTEN_PREFIX]
        suffix = listener_conf[CONF_LISTEN_SUFFIX]
        events = listener_conf[CONF_LISTEN_EVENTS]

        minio_listener = MinioListener(
            queue,
            get_minio_endpoint(host, port),
            access_key,
            secret_key,
            secure,
            bucket,
            prefix,
            suffix,
            events
        )

        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_START,
            minio_listener.start_handler
        )
        hass.bus.listen_once(
            EVENT_HOMEASSISTANT_STOP,
            minio_listener.stop_handler
        )

    for listen_conf in conf.get(CONF_LISTEN, []):
        _setup_listener(listen_conf)

    from minio import Minio

    minio_client = Minio(
        get_minio_endpoint(host, port),
        access_key,
        secret_key,
        secure
    )

    def _render_service_value(service, key):
        value = service.data.get(key)
        value.hass = hass
        return value.async_render()

    def put_file(service):
        """Upload file service."""
        bucket = _render_service_value(service, 'bucket')
        key = _render_service_value(service, 'key')
        file_path = _render_service_value(service, 'file_path')

        if not hass.config.is_allowed_path(file_path):
            _LOGGER.error('Invalid file_path %s', file_path)
            return

        minio_client.fput_object(bucket, key, file_path)

    def get_file(service):
        """Download file service."""
        bucket = _render_service_value(service, 'bucket')
        key = _render_service_value(service, 'key')
        file_path = _render_service_value(service, 'file_path')

        if not hass.config.is_allowed_path(file_path):
            _LOGGER.error('Invalid file_path %s', file_path)
            return

        minio_client.fget_object(bucket, key, file_path)

    def remove_file(service):
        """Delete file service."""
        bucket = _render_service_value(service, 'bucket')
        key = _render_service_value(service, 'key')

        minio_client.remove_object(bucket, key)

    hass.services.register(
        DOMAIN, 'put', put_file, schema=BUCKET_KEY_FILE_SCHEMA
    )
    hass.services.register(
        DOMAIN, 'get', get_file, schema=BUCKET_KEY_FILE_SCHEMA
    )
    hass.services.register(
        DOMAIN, 'remove', remove_file, schema=BUCKET_KEY_SCHEMA
    )

    return True
