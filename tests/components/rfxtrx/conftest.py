"""Common test tools."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components import rfxtrx
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


def create_rfx_test_cfg(device="abcd", automatic_add=False, devices=None):
    """Create rfxtrx config entry data."""
    return {
        "device": device,
        "host": None,
        "port": None,
        "automatic_add": automatic_add,
        "debug": False,
        "devices": devices,
    }


@pytest.fixture(autouse=True, name="rfxtrx")
async def rfxtrx_fixture(hass):
    """Fixture that cleans up threads from integration."""

    with patch("RFXtrx.Connect") as connect, patch("RFXtrx.DummyTransport2"):
        rfx = connect.return_value

        async def _signal_event(packet_id):
            event = rfxtrx.get_rfx_object(packet_id)
            await hass.async_add_executor_job(
                rfx.event_callback,
                event,
            )

            await hass.async_block_till_done()
            await hass.async_block_till_done()
            return event

        rfx.signal = _signal_event

        yield rfx


@pytest.fixture(name="rfxtrx_automatic")
async def rfxtrx_automatic_fixture(hass, rfxtrx):
    """Fixture that starts up with automatic additions."""
    entry_data = create_rfx_test_cfg(automatic_add=True, devices={})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
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
