"""Common test tools."""
from unittest import mock

import pytest

from homeassistant.components import rfxtrx


@pytest.fixture(autouse=True, name="rfxtrx")
async def rfxtrx_fixture(hass):
    """Fixture that cleans up threads from integration."""

    with mock.patch("RFXtrx.Connect") as connect, mock.patch("RFXtrx.DummyTransport2"):
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
