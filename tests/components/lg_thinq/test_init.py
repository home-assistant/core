"""Tests for the LG ThinQ integration."""

from unittest.mock import AsyncMock, patch

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
        AttributeError(),
        ThinQAPIException("1309", "error", None),
        TypeError(),
        ValueError(),
    ],
)
async def test_unload_entry_mqtt_disconnect_error(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test entry still unloads cleanly if the MQTT client fails to disconnect."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        return_value=True,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_config_entry.runtime_data.mqtt_client.client = AsyncMock(
        async_disconnect=AsyncMock(side_effect=exception)
    )

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("exception", [AttributeError(), TypeError(), ValueError()])
async def test_config_not_ready(
    hass: HomeAssistant,
    mock_thinq_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test for setup failure exception occurred."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
