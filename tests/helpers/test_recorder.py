"""Tests for the recorder helper."""

import pytest

from homeassistant.helpers import recorder

from tests.common import async_init_recorder_component


async def test_async_wait_for_recorder_full_startup_no_recorder(hass):
    """Test wait with no recorder when not loaded."""
    await recorder.async_wait_for_recorder_full_startup(hass)


async def test_async_wait_for_recorder_full_startup(hass):
    """Test wait with recorder when setup was successful."""
    await async_init_recorder_component(hass)
    await recorder.async_wait_for_recorder_full_startup(hass)
    assert await hass.data[recorder.DATA_INSTANCE].async_db_ready is True


async def test_async_wait_for_recorder_full_startup_when_setup_failed(hass):
    """Test wait with recorder when setup failed."""
    with pytest.raises(AssertionError):
        await async_init_recorder_component(hass, {"invalid_config": "invalid"})
    await recorder.async_wait_for_recorder_full_startup(hass)
