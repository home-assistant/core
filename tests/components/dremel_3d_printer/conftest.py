"""Define test fixtures for Dremel 3D Printer."""
from unittest.mock import MagicMock

import pytest

from homeassistant.const import CONF_HOST


@pytest.fixture(name="api")
def api():
    """Define a MagicMock for Dremel3DPrinter API."""
    return MagicMock(
        get_title=MagicMock(return_value="FooTitle"),
        get_serial_number=MagicMock(return_value="FooSN"),
    )


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
    }
