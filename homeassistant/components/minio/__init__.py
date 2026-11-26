"""Minio component."""

import logging
import os
from queue import Queue
import threading
from typing import override

import probatio

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_BUCKET, ATTR_KEY, DATA_MINIO, DOMAIN
from .minio_helper import MinioEventThread, create_minio_client
from .services import setup_services

_LOGGER = logging.getLogger(__name__)

CONF_ACCESS_KEY = "access_key"
CONF_SECRET_KEY = "secret_key"
CONF_SECURE = "secure"
CONF_LISTEN = "listen"
CONF_LISTEN_BUCKET = "bucket"
CONF_LISTEN_PREFIX = "prefix"
CONF_LISTEN_SUFFIX = "suffix"
CONF_LISTEN_EVENTS = "events"

DEFAULT_LISTEN_PREFIX = ""
DEFAULT_LISTEN_SUFFIX = ".*"
DEFAULT_LISTEN_EVENTS = "s3:ObjectCreated:*"

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_HOST): cv.string,
                probatio.Required(CONF_PORT): probatio.Port(),
                probatio.Required(CONF_ACCESS_KEY): cv.string,
                probatio.Required(probatio.Secret(CONF_SECRET_KEY)): cv.string,
                probatio.Required(CONF_SECURE): cv.boolean,
                probatio.Optional(CONF_LISTEN, default=[]): probatio.All(
                    probatio.EnsureList(),
                    [
                        probatio.Schema(
                            {
                                probatio.Required(CONF_LISTEN_BUCKET): cv.string,
                                probatio.Optional(
                                    CONF_LISTEN_PREFIX, default=DEFAULT_LISTEN_PREFIX
                                ): cv.string,
                                probatio.Optional(
                                    CONF_LISTEN_SUFFIX, default=DEFAULT_LISTEN_SUFFIX
                                ): cv.string,
                                probatio.Optional(
                                    CONF_LISTEN_EVENTS, default=DEFAULT_LISTEN_EVENTS
                                ): cv.string,
                            }
                        )
                    ],
                ),
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
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

    hass.data[DATA_MINIO] = create_minio_client(
        get_minio_endpoint(host, port), access_key, secret_key, secure
    )

    setup_services(hass)

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

    @override
    def run(self):
        """Listen to queue events, and forward them to Home Assistant event bus."""
        _LOGGER.debug("Running QueueListener")
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
        _LOGGER.debug("Stopping QueueListener")
        self._queue.put(None)
        self.join()
        _LOGGER.debug("Stopped QueueListener")

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
