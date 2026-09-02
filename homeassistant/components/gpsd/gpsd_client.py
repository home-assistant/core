"""Minimal threaded gpsd client for Home Assistant."""

import json
import select
import socket
import threading


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2947


class DataStream:
    """Holds the latest gpsd data with attribute access matching gps3.DataStream."""

    def __init__(self):
        self.mode = 0
        self.lat = "n/a"
        self.lon = "n/a"
        self.alt = "n/a"
        self.time = "n/a"
        self.speed = "n/a"
        self.climb = "n/a"
        self.satellites = "n/a"

    def _apply(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class GPSDClient:
    """Threaded gpsd client. API mirrors gps3.agps3threaded.AGPS3mechanism."""

    def __init__(self):
        self.data_stream = DataStream()
        self._sock = None
        self._thread = None
        self._running = False

    def stream_data(self, host=DEFAULT_HOST, port=DEFAULT_PORT, enable=True):
        if enable:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5)
            self._sock.connect((host, port))
            self._sock.sendall(b'?WATCH={"enable":true,"json":true}\n')
        else:
            self._running = False
            if self._sock:
                try:
                    self._sock.close()
                except OSError:
                    pass

    def run_thread(self):
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        buf = b""
        while self._running:
            try:
                ready = select.select([self._sock], [], [], 1.0)
                if not ready[0]:
                    continue
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        message = json.loads(line)
                        if message.get("class") in ("TPV", "SKY"):
                            self.data_stream._apply(message)
                    except json.JSONDecodeError:
                        pass
            except (socket.timeout, OSError):
                break
