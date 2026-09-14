"""Tests for the LG ThinQ integration."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
import pytest
from thinqconnect import ThinQAPIException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        return_value=True,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        ThinQAPIException(code="1309", message="Not allowed api call", headers={}),
        TypeError(),
        ValueError(),
        ClientError(),
        TimeoutError(),
    ],
)
async def test_unload_entry_with_failing_disconnect(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test the entry unloads even when telling LG we are leaving fails."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        return_value=True,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mqtt_client = mock_config_entry.runtime_data.mqtt_client
    mqtt_client.client = AsyncMock()
    mqtt_client.client.async_disconnect.side_effect = exception

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [AttributeError(), TypeError(), ValueError(), ClientError(), TimeoutError()],
)
async def test_config_not_ready_mqtt(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test for setup failure exception occurred during MQTT setup."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        ThinQAPIException(code="1309", message="Not allowed api call", headers={}),
        ClientError(),
        TimeoutError(),
    ],
)
async def test_config_not_ready_bridge_list(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test for setup failure exception occurred during coordinator setup."""
    with patch(
        "homeassistant.components.lg_thinq.async_get_ha_bridge_list",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
