"""Application class for Molohub."""
import asyncore
import logging
import threading
import time

from .const import (PING_INTERVAL_DEFAULT, RECONNECT_INTERVAL,
                    PROXY_TCP_CONNECTION_ACTIVATE_TIME)
from .utils import LOGGER


class MoloClientApp:
    """Application class for Molohub."""

    ping_thread = None
    main_thread = None
    is_exited = False
    ping_interval = PING_INTERVAL_DEFAULT
    last_activate_time = None

    def __init__(self):
        """Initialize application arguments."""
        self.molo_client = None
        self.local_session_dict = {}
        self.remote_session_dict = {}
        self.lock = threading.Lock()
        self.ping_buffer = None
        self.hass_context = None
        self.reset_activate_time()

    def proxy_loop(self):
        """Handle main loop and reconnection."""
        self.molo_client.sock_connect()
        while not self.is_exited:
            try:
                asyncore.loop()
            except asyncore.ExitNow as exc:
                logging.exception(exc)
                LOGGER.error("asyncore.loop exception")

            if not self.is_exited:
                asyncore.close_all()
                self.molo_client.sock_connect()
                time.sleep(RECONNECT_INTERVAL)
                LOGGER.info("moloserver reconnecting...")
        asyncore.close_all()
        LOGGER.debug("proxy exited")

    def run_reverse_proxy(self, hass, molo_client):
        """Start application main thread and ping thread."""
        self.hass_context = hass
        self.molo_client = molo_client
        self.ping_thread = threading.Thread(target=self.ping_server)
        self.ping_thread.setDaemon(True)
        self.ping_thread.start()

        self.main_thread = threading.Thread(target=self.proxy_loop)
        self.main_thread.setDaemon(True)
        self.main_thread.start()

    def ping_server(self):
        """Send ping to server every ping_interval."""
        while not self.is_exited:
            try:
                if self.molo_client:
                    self.set_ping_buffer(self.molo_client.ping_server_buffer())
                time.sleep(self.ping_interval)
            except EnvironmentError:
                break

            time_interval = time.time() - self.last_activate_time
            LOGGER.debug("data interval: %f", time_interval)
            if time_interval > PROXY_TCP_CONNECTION_ACTIVATE_TIME:
                LOGGER.info("connection timeout, reconnecting server")
                self.molo_client.handle_close()
                self.reset_activate_time()

    def reset_activate_time(self):
        """Reset last activate time for timeout."""
        self.last_activate_time = time.time()

    def set_ping_buffer(self, buffer):
        """Send ping."""
        with self.lock:
            self.ping_buffer = buffer

    def get_ping_buffer(self):
        """Get ping sending buffer."""
        if not self.ping_buffer:
            return None

        with self.lock:
            buffer = self.ping_buffer
            self.ping_buffer = None
            return buffer

    def stop_reverse_proxy(self):
        """Stop application, close all sessions."""
        LOGGER.debug("stopping reverse proxy")
        self.is_exited = True
        asyncore.close_all()


MOLO_CLIENT_APP = MoloClientApp()
