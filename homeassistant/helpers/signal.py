"""Signal handling related helpers."""
import logging
import signal
import sys
from types import FrameType

from homeassistant.const import RESTART_EXIT_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)


@callback
@bind_hass
def async_register_signal_handling(hass: HomeAssistant) -> None:
    """Register system signal handler for core."""
    if sys.platform != "win32":

        @callback
        def async_signal_handle(exit_code: int) -> None:
            """Wrap signal handling.

            * queue call to shutdown task
            * re-instate default handler
            """
            if exit_code == 2:
                # the signal SIGINT - Interrupt, need to be ignored on Android
                print("SIGINT")
                # quick stop access to files - to prevent
                # ProcessKiller: Process xxx (10754) has open file /mnt/media_rw/...
                # ProcessKiller: Sending Interrupt to process 10754
                from homeassistant.components.ais_dom import ais_global

                # 1. quick stop logs
                if ais_global.G_LOG_SETTINGS_INFO is not None:
                    # just to be sure
                    print("logging.shutdown")
                    logging.shutdown()
                    log = logging.getLogger()  # root logger
                    log.handlers.clear()
                    log.disabled = True
                    for hdlr in log.handlers[:]:  # remove all old handlers
                        hdlr.flush()
                        hdlr.close()
                        log.removeHandler(hdlr)
                    print("ais_stop_logs_event")
                    hass.bus.async_fire("ais_stop_logs_event")
                # 2. stop recorder if the db is in file
                if ais_global.G_DB_SETTINGS_INFO is not None:
                    db_url = ais_global.G_DB_SETTINGS_INFO["dbUrl"]
                    if db_url.startswith("sqlite://///data"):
                        print("ais_stop_recorder_event")
                        hass.bus.async_fire("ais_stop_recorder_event")
                # hass.loop.remove_signal_handler(signal.SIGINT)
            else:
                hass.loop.remove_signal_handler(signal.SIGTERM)
                hass.async_create_task(hass.async_stop(exit_code))

        try:
            hass.loop.add_signal_handler(signal.SIGTERM, async_signal_handle, 0)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGTERM")

        try:
            hass.loop.add_signal_handler(signal.SIGINT, async_signal_handle, 2)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGINT")

        try:
            hass.loop.add_signal_handler(
                signal.SIGHUP, async_signal_handle, RESTART_EXIT_CODE
            )
        except ValueError:
            _LOGGER.warning("Could not bind to SIGHUP")

    else:
        old_sigterm = None
        old_sigint = None

        @callback
        def async_signal_handle(exit_code: int, frame: FrameType) -> None:
            """Wrap signal handling.

            * queue call to shutdown task
            * re-instate default handler
            """
            signal.signal(signal.SIGTERM, old_sigterm)
            signal.signal(signal.SIGINT, old_sigint)
            hass.async_create_task(hass.async_stop(exit_code))

        try:
            old_sigterm = signal.signal(signal.SIGTERM, async_signal_handle)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGTERM")

        try:
            old_sigint = signal.signal(signal.SIGINT, async_signal_handle)
        except ValueError:
            _LOGGER.warning("Could not bind to SIGINT")
