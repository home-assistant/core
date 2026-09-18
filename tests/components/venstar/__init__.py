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
    ) -> None:
        """Initialize the Venstar library."""
        self.status = {}
        self.model = "COLORTOUCH"
        self._api_ver = 7
        self._firmware_ver = (5, 28)
        self.name = "TestVenstar"
        self._info = {}
        self._sensors = {}
        self.alerts = []
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
        self.name = "username"
        return True

    def broken_update_info(self):
        """Mock a update_info that raises Exception."""
        raise RequestException

    def failed_update_info(self):
        """Mock update_info returning False (silent failure)."""
        return False

    def update_sensors(self):
        """Mock update_sensors."""
        return True

    def failed_update_sensors(self):
        """Mock update_sensors returning False (silent failure)."""
        return False

    def update_runtimes(self):
        """Mock update_runtimes."""
        return True

    def update_alerts(self):
        """Mock update_alerts."""
        self.alerts = []
        return True

    def failed_update_alerts(self):
        """Mock update_alerts returning False (silent failure)."""
        return False

    def get_runtimes(self):
        """Mock get runtimes."""
        return [{"heat1": 100, "cool1": 200}]

    def failed_get_runtimes(self):
        """Mock get_runtimes returning False (silent failure)."""
        return False
