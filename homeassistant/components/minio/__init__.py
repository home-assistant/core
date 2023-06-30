"""Minio component."""
from __future__ import annotations

import logging
import os
from queue import Queue
import threading

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .minio_helper import MinioEventThread, create_minio_client

_LOGGER = logging.getLogger(__name__)

DOMAIN = "minio"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_ACCESS_KEY = "access_key"
CONF_SECRET_KEY = "secret_key"
CONF_SECURE = "secure"
CONF_LISTEN = "listen"
CONF_LISTEN_BUCKET = "bucket"
CONF_LISTEN_PREFIX = "prefix"
CONF_LISTEN_SUFFIX = "suffix"
CONF_LISTEN_EVENTS = "events"

ATTR_BUCKET = "bucket"
ATTR_KEY = "key"
ATTR_FILE_PATH = "file_path"

DEFAULT_LISTEN_PREFIX = ""
DEFAULT_LISTEN_SUFFIX = ".*"
DEFAULT_LISTEN_EVENTS = "s3:ObjectCreated:*"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_ACCESS_KEY): cv.string,
                vol.Required(CONF_SECRET_KEY): cv.string,
                vol.Required(CONF_SECURE): cv.boolean,
                vol.Optional(CONF_LISTEN, default=[]): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required(CONF_LISTEN_BUCKET): cv.string,
                                vol.Optional(
                                    CONF_LISTEN_PREFIX, default=DEFAULT_LISTEN_PREFIX
                                ): cv.string,
                                vol.Optional(
                                    CONF_LISTEN_SUFFIX, default=DEFAULT_LISTEN_SUFFIX
                                ): cv.string,
                                vol.Optional(
                                    CONF_LISTEN_EVENTS, default=DEFAULT_LISTEN_EVENTS
                                ): cv.string,
                            }
                        )
                    ],
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

BUCKET_KEY_SCHEMA = vol.Schema(
    {vol.Required(ATTR_BUCKET): cv.template, vol.Required(ATTR_KEY): cv.template}
)

BUCKET_KEY_FILE_SCHEMA = BUCKET_KEY_SCHEMA.extend(
    {vol.Required(ATTR_FILE_PATH): cv.template}
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up MinioClient and event listeners."""
    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    access_key = conf[CONF_ACCESS_KEY]
    secret_key = conf[CONF_SECRET_KEY]
    secure = conf[CONF_SECURE]

    queue_listener = QueueListener(hass)
    queue = queue_listener.queue

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, queue_listener.start_handler)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, queue_listener.stop_handler)

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
            events,
        )

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, minio_listener.start_handler)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, minio_listener.stop_handler)

    for listen_conf in conf[CONF_LISTEN]:
        _setup_listener(listen_conf)

    minio_client = create_minio_client(
        get_minio_endpoint(host, port), access_key, secret_key, secure
    )

    def _render_service_value(service, key):
        value = service.data[key]
        value.hass = hass
        return value.async_render(parse_result=False)

    def put_file(service: ServiceCall) -> None:
        """Upload file service."""
        bucket = _render_service_value(service, ATTR_BUCKET)
        key = _render_service_value(service, ATTR_KEY)
        file_path = _render_service_value(service, ATTR_FILE_PATH)

        if not hass.config.is_allowed_path(file_path):
            raise ValueError(f"Invalid file_path {file_path}")

        minio_client.fput_object(bucket, key, file_path)

    def get_file(service: ServiceCall) -> None:
        """Download file service."""
        bucket = _render_service_value(service, ATTR_BUCKET)
        key = _render_service_value(service, ATTR_KEY)
        file_path = _render_service_value(service, ATTR_FILE_PATH)

        if not hass.config.is_allowed_path(file_path):
            raise ValueError(f"Invalid file_path {file_path}")

        minio_client.fget_object(bucket, key, file_path)

    def remove_file(service: ServiceCall) -> None:
        """Delete file service."""
        bucket = _render_service_value(service, ATTR_BUCKET)
        key = _render_service_value(service, ATTR_KEY)

        minio_client.remove_object(bucket, key)

    hass.services.register(DOMAIN, "put", put_file, schema=BUCKET_KEY_FILE_SCHEMA)
    hass.services.register(DOMAIN, "get", get_file, schema=BUCKET_KEY_FILE_SCHEMA)
    hass.services.register(DOMAIN, "remove", remove_file, schema=BUCKET_KEY_SCHEMA)

    return True


def get_minio_endpoint(host: str, port: int) -> str:
    """Create minio endpoint from host and port."""
    return f"{host}:{port}"


class QueueListener(threading.Thread):
    """Forward events from queue into Home Assistant event bus."""

    def __init__(self, hass):
        """Create queue."""
        super().__init__()
        self._hass = hass
        self._queue = Queue()

    def run(self):
        """Listen to queue events, and forward them to Home Assistant event bus."""
        _LOGGER.info("Running QueueListener")
        while True:
            if (event := self._queue.get()) is None:
                break

            _, file_name = os.path.split(event[ATTR_KEY])

            _LOGGER.debug(
                "Sending event %s, %s, %s",
                event["event_name"],
                event[ATTR_BUCKET],
                event[ATTR_KEY],
            )
            self._hass.bus.fire(DOMAIN, {"file_name": file_name, **event})

    @property
    def queue(self):
        """Return wrapped queue."""
        return self._queue

    def stop(self):
        """Stop run by putting None into queue and join the thread."""
        _LOGGER.info("Stopping QueueListener")
        self._queue.put(None)
        self.join()
        _LOGGER.info("Stopped QueueListener")

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
        events: list[str],
    ) -> None:
        """Create Listener."""
        self._queue = queue
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._bucket_name = bucket_name
        self._prefix = prefix
        self._suffix = suffix
        self._events = events
        self._minio_event_thread = None

    def start_handler(self, _):
        """Create and start the event thread."""
        self._minio_event_thread = MinioEventThread(
            self._queue,
            self._endpoint,
            self._access_key,
            self._secret_key,
            self._secure,
            self._bucket_name,
            self._prefix,
            self._suffix,
            self._events,
        )
        self._minio_event_thread.start()

    def stop_handler(self, _):
        """Issue stop and wait for thread to join."""
        if self._minio_event_thread is not None:
            self._minio_event_thread.stop()
