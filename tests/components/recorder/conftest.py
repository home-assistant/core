"""Common test tools."""

import pytest

from homeassistant.components.recorder.const import DATA_INSTANCE

from tests.common import init_recorder_component


@pytest.fixture
def hass_recorder(hass):
    """Home Assistant fixture with in-memory recorder."""

    async def setup_recorder(config=None):
        """Set up with params."""
        await hass.async_add_executor_job(
            init_recorder_component, hass, config
        )  # force in memory db

        await hass.async_block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
