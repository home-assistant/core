"""Support for Obihai Connectivity."""

from __future__ import annotations

from pyobihai import PyObihai

from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, LOGGER


def get_pyobihai(
    host: str,
    username: str,
    password: str,
) -> PyObihai:
    """Retrieve an authenticated PyObihai."""

    return PyObihai(host, username, password)


def validate_auth(
    host: str,
    username: str,
    password: str,
) -> PyObihai | None:
    """Test if the given setting works as expected."""

    obi = get_pyobihai(host, username, password)

    login = obi.check_account()
    if not login:
        LOGGER.debug("Invalid credentials")
        return None

    return obi


class ObihaiConnection:
    """Contains a list of Obihai Sensors."""

    def __init__(
        self,
        host: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
    ) -> None:
        """Store configuration."""
        self.sensors: list = []
        self.host = host
        self.username = username
        self.password = password
        self.serial: str
        self.services: list = []
        self.line_services: list = []
        self.call_direction: list = []
        self.pyobihai: PyObihai = None
        self.available: bool = True

    def update(self) -> bool:
        """Validate connection and retrieve a list of sensors."""

        if not self.pyobihai:
            self.pyobihai = validate_auth(self.host, self.username, self.password)

            if not self.pyobihai:
                return False

        self.serial = self.pyobihai.get_device_serial()
        self.services = self.pyobihai.get_state()
        self.line_services = self.pyobihai.get_line_state()
        self.call_direction = self.pyobihai.get_call_direction()

        return True
