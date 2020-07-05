"""Common test tools."""
import threading
from unittest import mock

import RFXtrx
import pytest

from homeassistant.components import rfxtrx as rfxtrx_core

from tests.common import mock_component


class FixedDummySerial(RFXtrx._dummySerial):  # pylint: disable=protected-access
    """Fixed dummy serial that doesn't cause max CPU usage."""

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        self._close_event = threading.Event()

    def read(self, data=None):
        """Read."""
        res = super().read(data)
        if not res and not data:
            self._close_event.wait(0.1)
        return res

    def close(self):
        """Close."""
        self._close_event.set()


class FixedDummyTransport(RFXtrx.DummyTransport):
    """Fixed dummy transport that maxes CPU."""

    def __init__(self, device="", debug=True):
        """Init."""
        super().__init__(device, debug)
        self._close_event = threading.Event()

    def receive_blocking(self, data=None):
        """Read."""
        res = super().receive_blocking(data)
        if not res:
            self._close_event.wait(0.1)
        return res

    def close(self):
        """Close."""
        self._close_event.set()


@pytest.fixture(autouse=True)
async def rfxtrx_cleanup():
    """Fixture that cleans up threads from integration."""

    with mock.patch("RFXtrx._dummySerial", new=FixedDummySerial), mock.patch(
        "RFXtrx.DummyTransport", new=FixedDummyTransport
    ):
        yield

    rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS.clear()
    rfxtrx_core.RFX_DEVICES.clear()


@pytest.fixture(name="rfxtrx")
async def rfxtrx_fixture(hass):
    """Stub out core rfxtrx to test platform."""
    mock_component(hass, "rfxtrx")

    rfxobject = mock.MagicMock()
    hass.data[rfxtrx_core.DATA_RFXOBJECT] = rfxobject

    yield rfxobject

    # These test don't listen for stop to do cleanup.
    if rfxtrx_core.DATA_RFXOBJECT in hass.data:
        hass.data[rfxtrx_core.DATA_RFXOBJECT].close_connection()
