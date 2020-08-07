"""Common test tools."""
from datetime import timedelta

import pytest

from homeassistant.components import rfxtrx
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True, name="rfxtrx")
async def rfxtrx_fixture(hass):
    """Fixture that cleans up threads from integration."""

    with patch("RFXtrx.Connect") as connect, patch("RFXtrx.DummyTransport2"):
        rfx = connect.return_value

        async def _signal_event(packet_id):
            event = rfxtrx.get_rfx_object(packet_id)
            await hass.async_add_executor_job(
                rfx.event_callback, event,
            )

            await hass.async_block_till_done()
            await hass.async_block_till_done()
            return event

        rfx.signal = _signal_event

        yield rfx


@pytest.fixture(name="rfxtrx_automatic")
async def rfxtrx_automatic_fixture(hass, rfxtrx):
    """Fixture that starts up with automatic additions."""

    assert await async_setup_component(
        hass, "rfxtrx", {"rfxtrx": {"device": "abcd", "automatic_add": True}},
    )
    await hass.async_block_till_done()
    await hass.async_start()
    yield rfxtrx


@pytest.fixture
async def timestep(hass):
    """Step system time forward."""

    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = utcnow()

        async def delay(seconds):
            """Trigger delay in system."""
            mock_utcnow.return_value += timedelta(seconds=seconds)
            async_fire_time_changed(hass, mock_utcnow.return_value)
            await hass.async_block_till_done()

        yield delay
