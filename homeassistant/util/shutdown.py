"""Shutdown Home Assistant."""

import logging
import threading

SHUTDOWN_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


def deadlock_safe_shutdown() -> None:
    """Shutdown that will not deadlock."""
    # threading._shutdown can deadlock forever
    # see https://github.com/justengel/continuous_threading#shutdown-update
    # for additional detail
    for thread in threading.enumerate():
        try:
            if (
                thread is not threading.main_thread()
                and thread.is_alive()
                and not thread.daemon
            ):
                thread.join(SHUTDOWN_TIMEOUT)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Failed to join thread: %s", err)
