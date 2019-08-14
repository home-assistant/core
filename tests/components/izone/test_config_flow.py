"""Tests for iZone."""

from asyncio import Event
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import izone
from homeassistant.components.izone.const import DATA_DISCOVERY_SERVICE

from tests.common import mock_coro


@pytest.fixture
def mock_disco():
    """Mock discovery service."""
    disco = Mock()
    disco.controllers = {}
    disco.controller_ready = Event()
    disco.controller_ready.set()
    yield disco


async def test_not_found(hass, mock_disco):
    """Test not finding iZone controller."""
    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.izone.discovery." "async_start_discovery_service",
        return_value=mock_coro(mock_disco),
    ), patch(
        "homeassistant.components.izone.discovery." "async_stop_discovery_service",
        return_value=mock_coro(),
    ):
        result = await hass.config_entries.flow.async_init(
            izone.IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

        await hass.async_block_till_done()

    mock_setup.assert_not_called()


async def test_found(hass, mock_disco):
    """Test not finding iZone controller."""
    mock_disco.controllers["blah"] = object()
    hass.data[DATA_DISCOVERY_SERVICE] = mock_disco
    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.izone.discovery." "async_start_discovery_service",
        return_value=mock_coro(mock_disco),
    ), patch(
        "homeassistant.components.izone.discovery." "async_stop_discovery_service",
        return_value=mock_coro(),
    ):
        result = await hass.config_entries.flow.async_init(
            izone.IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    mock_setup.assert_called_once()
