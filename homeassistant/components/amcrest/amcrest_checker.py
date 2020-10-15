"""Support for Amcrest IP cameras amcrest checker"""
from datetime import timedelta
import logging
import threading

from amcrest import AmcrestError, Http, LoginError

from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

from .const import COMM_RETRIES, COMM_TIMEOUT, SERVICE_UPDATE
from .helpers import service_signal

_LOGGER = logging.getLogger(__name__)

MAX_ERRORS = 5
RECHECK_INTERVAL = timedelta(minutes=1)


class AmcrestChecker(Http):
    """amcrest.Http wrapper for catching errors."""

    def __init__(self, hass, name, host, port, user, password):
        """Initialize."""
        self._hass = hass
        self._wrap_name = name
        self._wrap_errors = 0
        self._wrap_lock = threading.Lock()
        self._wrap_login_err = False
        self._wrap_event_flag = threading.Event()
        self._wrap_event_flag.set()
        self._unsub_recheck = None
        super().__init__(
            host,
            port,
            user,
            password,
            retries_connection=COMM_RETRIES,
            timeout_protocol=COMM_TIMEOUT,
        )

    @property
    def available(self):
        """Return if camera's API is responding."""
        return self._wrap_errors <= MAX_ERRORS and not self._wrap_login_err

    @property
    def available_flag(self):
        """Return threading event flag that indicates if camera's API is responding."""
        return self._wrap_event_flag

    def _start_recovery(self):
        """Start Recovery after offline period"""
        self._wrap_event_flag.clear()
        dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._wrap_name))
        self._unsub_recheck = track_time_interval(
            self._hass, self._wrap_test_online, RECHECK_INTERVAL
        )

    def command(self, *args, **kwargs):
        """amcrest.Http.command wrapper to catch errors."""
        try:
            ret = super().command(*args, **kwargs)
        except LoginError as ex:
            with self._wrap_lock:
                was_online = self.available
                was_login_err = self._wrap_login_err
                self._wrap_login_err = True
            if not was_login_err:
                _LOGGER.error("%s camera offline: Login error: %s", self._wrap_name, ex)
            if was_online:
                self._start_recovery()
            raise
        except AmcrestError:
            with self._wrap_lock:
                was_online = self.available
                errs = self._wrap_errors = self._wrap_errors + 1
                offline = not self.available
            _LOGGER.debug("%s camera errs: %i", self._wrap_name, errs)
            if was_online and offline:
                _LOGGER.error("%s camera offline: Too many errors", self._wrap_name)
                self._start_recovery()
            raise
        with self._wrap_lock:
            was_offline = not self.available
            self._wrap_errors = 0
            self._wrap_login_err = False
        if was_offline:
            self._unsub_recheck()
            self._unsub_recheck = None
            _LOGGER.error("%s camera back online", self._wrap_name)
            self._wrap_event_flag.set()
            dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._wrap_name))
        return ret

    def _wrap_test_online(self, now):
        """Test if camera is back online."""
        _LOGGER.debug("Testing if %s back online", self._wrap_name)
        try:
            self.current_time
        except AmcrestError:
            pass
