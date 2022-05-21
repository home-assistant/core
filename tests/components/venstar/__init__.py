"""Tests for the venstar integration."""
from requests import RequestException


class VenstarColorTouchMock:
    """Mock Venstar Library."""

    def __init__(
        self,
        addr,
        timeout,
        user=None,
        password=None,
        pin=None,
        proto="http",
        SSLCert=False,
    ):
        """Initialize the Venstar library."""
        self.status = {}
        self.model = "COLORTOUCH"
        self._api_ver = 5
        self.name = "TestVenstar"
        self._info = {}
        self._sensors = {}
        self.alerts = {}
        self.MODE_OFF = 0
        self.MODE_HEAT = 1
        self.MODE_COOL = 2
        self.MODE_AUTO = 3
        self._type = "residential"

    def login(self):
        """Mock login."""
        return True

    def _request(self, path, data=None):
        """Mock request."""
        self.status = {}

    def update(self):
        """Mock update."""
        return True

    def update_info(self):
        """Mock update_info."""
        return True

    def broken_update_info(self):
        """Mock a update_info that raises Exception."""
        raise RequestException

    def update_sensors(self):
        """Mock update_sensors."""
        return True

    def update_runtimes(self):
        """Mock update_runtimes."""
        return True

    def update_alerts(self):
        """Mock update_alerts."""
        return True

    def get_runtimes(self):
        """Mock get runtimes."""
        return {}
