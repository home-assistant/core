"""Component to create an interface to a Pilight daemon."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import functools
import logging
import threading
from typing import Any

from pilight import pilight
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_WHITELIST,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_SEND_DELAY = "send_delay"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
DEFAULT_SEND_DELAY = 0.0
DOMAIN = "pilight"

EVENT = "pilight_received"

# The Pilight code schema depends on the protocol. Thus only require to have
# the protocol information. Ensure that protocol is in a list otherwise
# segfault in pilight-daemon, https://github.com/pilight/pilight/issues/296
RF_CODE_SCHEMA = vol.Schema(
    {vol.Required(CONF_PROTOCOL): vol.All(cv.ensure_list, [cv.string])},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_NAME = "send"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_WHITELIST, default={}): {cv.string: [cv.string]},
                vol.Optional(CONF_SEND_DELAY, default=DEFAULT_SEND_DELAY): vol.Coerce(
                    float
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Pilight component."""

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    send_throttler = CallRateDelayThrottle(hass, config[DOMAIN][CONF_SEND_DELAY])

    try:
        pilight_client = pilight.Client(host=host, port=port)
    except (OSError, TimeoutError) as err:
        _LOGGER.error("Unable to connect to %s on port %s: %s", host, port, err)
        return False

    def start_pilight_client(_):
        """Run when Home Assistant starts."""
        pilight_client.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_pilight_client)

    def stop_pilight_client(_):
        """Run once when Home Assistant stops."""
        pilight_client.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_pilight_client)

    @send_throttler.limited
    def send_code(call: ServiceCall) -> None:
        """Send RF code to the pilight-daemon."""
        # Change type to dict from mappingproxy since data has to be JSON
        # serializable
        message_data = dict(call.data)

        try:
            pilight_client.send_code(message_data)
        except OSError:
            _LOGGER.error("Pilight send failed for %s", str(message_data))

    hass.services.register(DOMAIN, SERVICE_NAME, send_code, schema=RF_CODE_SCHEMA)

    # Publish received codes on the HA event bus
    # A whitelist of codes to be published in the event bus
    whitelist = config[DOMAIN].get(CONF_WHITELIST)

    def handle_received_code(data):
        """Run when RF codes are received."""
        # Unravel dict of dicts to make event_data cut in automation rule
        # possible
        data = dict(
            {"protocol": data["protocol"], "uuid": data["uuid"]}, **data["message"]
        )

        # No whitelist defined or data matches whitelist, put data on event bus
        if not whitelist or all(str(data[key]) in whitelist[key] for key in whitelist):
            hass.bus.fire(EVENT, data)

    pilight_client.set_callback(handle_received_code)

    return True


class CallRateDelayThrottle:
    """Helper class to provide service call rate throttling.

    This class provides a decorator to decorate service methods that need
    to be throttled to not exceed a certain call rate per second.
    One instance can be used on multiple service methods to archive
    an overall throttling.

    As this uses track_point_in_utc_time to schedule delayed executions
    it should not block the mainloop.
    """

    def __init__(self, hass: HomeAssistant, delay_seconds: float) -> None:
        """Initialize the delay handler."""
        self._delay = timedelta(seconds=max(0.0, delay_seconds))
        self._queue: list[Callable[[Any], None]] = []
        self._active = False
        self._lock = threading.Lock()
        self._next_ts = dt_util.utcnow()
        self._schedule = functools.partial(track_point_in_utc_time, hass)

    def limited[**_P](self, method: Callable[_P, Any]) -> Callable[_P, None]:
        """Decorate to delay calls on a certain method."""

        @functools.wraps(method)
        def decorated(*args: _P.args, **kwargs: _P.kwargs) -> None:
            """Delay a call."""
            if self._delay.total_seconds() == 0.0:
                method(*args, **kwargs)
                return

            def action(event: Any) -> None:
                """Wrap an action that gets scheduled."""
                method(*args, **kwargs)

                with self._lock:
                    self._next_ts = dt_util.utcnow() + self._delay

                    if not self._queue:
                        self._active = False
                    else:
                        next_action = self._queue.pop(0)
                        self._schedule(next_action, self._next_ts)

            with self._lock:
                if self._active:
                    self._queue.append(action)
                else:
                    self._active = True
                    schedule_ts = max(dt_util.utcnow(), self._next_ts)
                    self._schedule(action, schedule_ts)

        return decorated
