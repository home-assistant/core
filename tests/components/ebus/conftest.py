"""Test Configuration."""
from unittest.mock import patch

from pyebus import OK
import pytest

from .const import HOST, MSGDEFCODES, PORT


@pytest.fixture(name="ebus")
def mock_ebus():
    """Mock a successful ebus."""
    with patch("homeassistant.components.ebus.config_flow.Ebus") as ebus_mock:

        async def async_return_ok():
            return OK

        async def async_return_none():
            return None

        ebus_mock.return_value.host = HOST
        ebus_mock.return_value.port = PORT
        ebus_mock.return_value.async_is_online = async_return_ok
        ebus_mock.return_value.async_wait_scancompleted = async_return_none
        ebus_mock.return_value.async_load_msgdefs = async_return_none
        ebus_mock.return_value.async_load_circuitinfos = async_return_none
        ebus_mock.return_value.msgdefcodes = MSGDEFCODES
        yield ebus_mock
