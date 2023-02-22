"""Support for Obihai Sensors."""
from __future__ import annotations

from pyobihai import PyObihai

from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, LOGGER
from .sensor import ObihaiServiceSensors


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
) -> bool:
    """Test if the given setting works as expected."""
    obi = get_pyobihai(host, username, password)

    login = obi.check_account()
    if not login:
        LOGGER.debug("Invalid credentials")
        return False

    return True


class ObihaiConnection:
    """Contains a list of Obihai Sensors."""

    def __init__(
        self,
        host: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
    ) -> None:
        """Store configuration."""
        self.sensors: list[ObihaiServiceSensors] = []
        self.host = host
        self.username = username
        self.password = password

    def update(self) -> bool:
        """Validate connection and retrieve a list of sensors."""
        pyobihai = get_pyobihai(self.host, self.username, self.password)

        if not pyobihai.check_account():
            return False

        serial = pyobihai.get_device_serial()
        services = pyobihai.get_state()
        line_services = pyobihai.get_line_state()
        call_direction = pyobihai.get_call_direction()

        for key in services:
            self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        if line_services is not None:
            for key in line_services:
                self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        for key in call_direction:
            self.sensors.append(ObihaiServiceSensors(pyobihai, serial, key))

        return True
