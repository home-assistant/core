"""Tests for the recorder helper."""

from unittest.mock import patch

import pytest

from homeassistant.components import recorder
from homeassistant.helpers.recorder import (
    DATA_INSTANCE,
    async_wait_for_recorder_full_startup,
)
from homeassistant.setup import async_setup_component

from tests.common import async_init_recorder_component


async def test_async_wait_for_recorder_full_startup_no_recorder(hass):
    """Test wait with no recorder when not loaded."""
    await async_wait_for_recorder_full_startup(hass)


async def test_async_wait_for_recorder_full_startup(hass):
    """Test wait with recorder when setup was successful."""
    await async_init_recorder_component(hass)
    await async_wait_for_recorder_full_startup(hass)
    assert await hass.data[DATA_INSTANCE].async_db_ready is True


async def test_async_wait_for_recorder_full_startup_when_setup_failed(hass):
    """Test wait with recorder when setup failed."""
    with pytest.raises(AssertionError):
        await async_init_recorder_component(hass, {"invalid_config": "invalid"})
    await async_wait_for_recorder_full_startup(hass)


async def test_async_wait_for_recorder_full_startup_when_setup_failed_in_db_connect(
    hass,
):
    """Test wait with recorder when setup failed in the db init phase."""
    with patch("homeassistant.components.recorder.migration.migrate_schema"), patch(
        "homeassistant.components.recorder.time.sleep"
    ):
        await async_setup_component(
            hass,
            recorder.DOMAIN,
            {
                recorder.DOMAIN: {
                    recorder.CONF_DB_URL: "sqlite:///file/that/cannot/exist/on/this/system"
                }
            },
        )
    await async_wait_for_recorder_full_startup(hass)
