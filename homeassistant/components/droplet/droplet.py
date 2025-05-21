"""Module to communicate with Droplet device."""

import contextlib
import json
import socket
import threading


class Droplet:
    """Server to communicate with Droplet."""

    def __init__(self, port, ip_addr, callback, timeout=10):
        """Initialize Droplet server."""
        self.port = 3333
        self.ip_addr = "localhost"
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(timeout)
        self.callback = callback
        self.flow = 0
        self.stop_serve = threading.Event()
        self.start()

    def start(self):
        """Bind to socket and start server."""
        with contextlib.suppress(OSError):
            self.socket.bind(("", self.port))
        self.socket.listen()
        threading.Thread(target=self.run_server, daemon=True).start()

    def stop(self):
        """Stop listening for flows."""
        self.stop_serve.set()

    def _set_flow(self, flow):
        if flow is not None:
            self.flow = flow
            self.callback(flow)

    # How to accommodate multiple droplets???
    def run_server(self):
        """Listen for flows."""
        self.stop_serve.clear()
        while True:
            try:
                if self.stop_serve.is_set():
                    return
                conn, address = self.socket.accept()
                while True:
                    if self.stop_serve.is_set():
                        return
                    data = conn.recv(1024)
                    if data:
                        try:
                            msg = json.loads(data)
                            self._set_flow(msg.get("flow"))
                        except json.JSONDecodeError:
                            pass
            except TimeoutError:
                pass
