"""Common test tools."""
from unittest import mock

import pytest


@pytest.fixture(autouse=True, name="rfxtrx")
async def rfxtrx(hass):
    """Fixture that cleans up threads from integration."""

    with mock.patch("RFXtrx.Connect") as connect, mock.patch("RFXtrx.DummyTransport2"):
        yield connect.return_value
