"""Signal handling related helpers."""
import logging
import signal
import sys

from homeassistant.core import callback
from homeassistant.const import RESTART_EXIT_CODE
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)


@callback
@bind_hass
def async_register_signal_handling(hass):
    """Register system signal handler for core."""
    if sys.platform != 'win32':
        @callback
        def async_signal_handle(exit_code):
            """Wrap signal handling."""
            hass.async_add_job(hass.async_stop(exit_code))

        try:
            hass.loop.add_signal_handler(
                signal.SIGTERM, async_signal_handle, 0)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGTERM")

        try:
            hass.loop.add_signal_handler(
                signal.SIGHUP, async_signal_handle, RESTART_EXIT_CODE)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGHUP")
