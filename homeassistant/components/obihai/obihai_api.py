"""Support for Obihai Sensors."""
from __future__ import annotations

from pyobihai import PyObihai

from .const import LOGGER


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
