"""The tests for the emoncms_history init."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import CONF_API_KEY, CONF_URL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_valid_config(hass: HomeAssistant) -> None:
    """Test setting up the emoncms_history component with valid configuration."""
    config = {
        "emoncms_history": {
            CONF_API_KEY: "dummy",
            CONF_URL: "https://emoncms.example",
            "inputnode": 42,
            "whitelist": ["sensor.temp"],
        }
    }
    # Simulate a sensor
    hass.states.async_set("sensor.temp", "23.4", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "emoncms_history", config)
    await hass.async_block_till_done()


async def test_setup_missing_config(hass: HomeAssistant) -> None:
    """Test setting up the emoncms_history component with missing configuration."""
    config = {"emoncms_history": {"api_key": "dummy"}}
    success = await async_setup_component(hass, "emoncms_history", config)
    assert not success


@pytest.fixture
async def emoncms_client() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms client with successful responses."""
    with patch(
        "homeassistant.components.emoncms_history.EmoncmsClient", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.async_input_post.return_value = '{"success": true}'
        yield client


async def test_emoncms_send_data(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending data to Emoncms with and without success."""

    config = {
        "emoncms_history": {
            "api_key": "dummy",
            "url": "http://fake-url",
            "inputnode": 42,
            "whitelist": ["sensor.temp"],
        }
    }

    assert await async_setup_component(hass, "emoncms_history", config)
    await hass.async_block_till_done()

    for state in None, "", STATE_UNAVAILABLE, STATE_UNKNOWN:
        hass.states.async_set("sensor.temp", state, {"unit_of_measurement": "°C"})
        await hass.async_block_till_done()

        freezer.tick(timedelta(seconds=60))
        await hass.async_block_till_done()

        assert emoncms_client.async_input_post.call_args is None

    hass.states.async_set("sensor.temp", "not_a_number", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    emoncms_client.async_input_post.assert_not_called()

    hass.states.async_set("sensor.temp", "23.4", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    emoncms_client.async_input_post.assert_called_once()
    assert emoncms_client.async_input_post.return_value == '{"success": true}'

    _, kwargs = emoncms_client.async_input_post.call_args
    assert kwargs["data"] == {"sensor.temp": 23.4}
    assert kwargs["node"] == "42"

    emoncms_client.async_input_post.side_effect = aiohttp.ClientError(
        "Connection refused"
    )
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    assert any(
        "Network error when sending data to Emoncms" in message
        for message in caplog.text.splitlines()
    )

    emoncms_client.async_input_post.side_effect = ValueError("Invalid value format")

    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    assert any(
        "Value error when preparing data for Emoncms" in message
        for message in caplog.text.splitlines()
    )


async def test_emoncms_send_data_legacy_mode(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending data to Emoncms in legacy mode (string payload)."""

    config = {
        "emoncms_history": {
            "api_key": "dummy",
            "url": "http://fake-url",
            "inputnode": 99,
            "whitelist": ["sensor.temp"],
            "legacy_mode": 1,
        }
    }

    assert await async_setup_component(hass, "emoncms_history", config)
    await hass.async_block_till_done()

    # Set valid state
    hass.states.async_set("sensor.temp", "42.0", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    emoncms_client.async_input_post.assert_called_once()

    args, kwargs = emoncms_client.async_input_post.call_args
    # Legacy mode → payload string wrapped in {}
    assert args[0] == "{sensor.temp:42.0}"
    assert kwargs["node"] == "99"
