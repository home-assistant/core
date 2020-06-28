"""Common test tools."""
import pytest

from homeassistant.components import rfxtrx as rfxtrx_core

from tests.common import mock_component


@pytest.fixture(autouse=True)
async def rfxtrx_cleanup(hass):
    """Fixture that cleans up threads from integration."""
    yield
    rfxtrx_core.RECEIVED_EVT_SUBSCRIBERS.clear()
    rfxtrx_core.RFX_DEVICES.clear()
    if rfxtrx_core.DATA_RFXOBJECT in hass.data:
        hass.data[rfxtrx_core.DATA_RFXOBJECT].close_connection()


@pytest.fixture(name="rfxtrx")
async def rfxtrx_fixture(hass):
    """Stub out core rfxtrx to test platform."""
    mock_component(hass, "rfxtrx")
