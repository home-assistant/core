"""Tests for Escea."""

from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.escea.const import DISPATCH_CONTROLLER_DISCOVERED, ESCEA
from homeassistant.helpers.dispatcher import async_dispatcher_send


@pytest.fixture
def mock_discovery_service():
    """Mock discovery service."""
    discovery_service = Mock()
    discovery_service.controllers = {}
    yield discovery_service


def _mock_start_discovery(hass, mock_discovery_service):
    def do_discovered(*args):
        async_dispatcher_send(hass, DISPATCH_CONTROLLER_DISCOVERED, True)
        return mock_discovery_service

    return do_discovered


async def test_not_found(hass, mock_discovery_service):
    """Test not finding Escea controller."""

    with patch(
        "homeassistant.components.escea.config_flow.async_start_discovery_service"
    ) as start_discovery_service, patch(
        "homeassistant.components.escea.config_flow.async_stop_discovery_service",
        return_value=None,
    ) as stop_discovery_service:
        start_discovery_service.side_effect = _mock_start_discovery(
            hass, mock_discovery_service
        )
        result = await hass.config_entries.flow.async_init(
            ESCEA, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

        await hass.async_block_till_done()

    stop_discovery_service.assert_called_once()


async def test_found(hass, mock_discovery_service):
    """Test not finding Escea controller."""
    mock_discovery_service.controllers["blah"] = object()

    with patch(
        "homeassistant.components.escea.climate.async_setup_entry",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.escea.config_flow.async_start_discovery_service"
    ) as start_discovery_service, patch(
        "homeassistant.components.escea.async_start_discovery_service",
        return_value=None,
    ):
        start_discovery_service.side_effect = _mock_start_discovery(
            hass, mock_discovery_service
        )
        result = await hass.config_entries.flow.async_init(
            ESCEA, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    mock_setup.assert_called_once()
