"""Tests for the Honeywell Lyric config flow."""
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.lyric import config_flow
from homeassistant.components.lyric.const import (
    DATA_LYRIC_CONFIG,
    DOMAIN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
)
from homeassistant.setup import async_setup_component

from tests.common import MockDependency

FIXTURE_APP = {
    DOMAIN: {CONF_CLIENT_ID: "1234567890abcdef", CONF_CLIENT_SECRET: "1234567890abcdef"}
}

FIXTURE_API = {"api": {"base_url": "http://localhost:8123"}}


@pytest.fixture
def mock_lyriclib():
    """Mock lyric."""
    with MockDependency("lyric") as mock_lyriclib_:
        yield mock_lyriclib_


async def setup_component(hass):
    """Set up Honeywell Lyric component."""
    with patch("os.path.isfile", return_value=False):
        assert await async_setup_component(hass, "api", FIXTURE_API)
        assert await async_setup_component(hass, DOMAIN, FIXTURE_APP)
        await hass.async_block_till_done()


async def test_lyric_abort(hass, mock_lyriclib):
    """Test abort on mising config."""
    await setup_component(hass)

    flow = config_flow.LyricFlowHandler()
    flow.hass = hass

    flow.hass.data[DATA_LYRIC_CONFIG] = None

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_config"


async def test_lyric_setup(hass, mock_lyriclib):
    """Test abort on Lyric error."""
    await setup_component(hass)

    flow = config_flow.LyricFlowHandler()
    flow.hass = hass

    flow.flow_id = "1234567890abcdef"

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
