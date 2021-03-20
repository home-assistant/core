"""Tests for iZone."""

from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.izone.const import DISPATCH_CONTROLLER_DISCOVERED, IZONE


@pytest.fixture
def mock_disco():
    """Mock discovery service."""
    disco = Mock()
    disco.pi_disco = Mock()
    disco.pi_disco.controllers = {}
    yield disco


def _mock_start_discovery(hass, mock_disco):
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    def do_disovered(*args):
        async_dispatcher_send(hass, DISPATCH_CONTROLLER_DISCOVERED, True)
        return mock_disco

    return do_disovered


async def test_not_found(hass, mock_disco):
    """Test not finding iZone controller."""

    with patch(
        "homeassistant.components.izone.config_flow.async_start_discovery_service"
    ) as start_disco, patch(
        "homeassistant.components.izone.config_flow.async_stop_discovery_service",
        return_value=None,
    ) as stop_disco:
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

        await hass.async_block_till_done()

    stop_disco.assert_called_once()


async def test_found(hass, mock_disco):
    """Test not finding iZone controller."""
    mock_disco.pi_disco.controllers["blah"] = object()

    with patch(
        "homeassistant.components.izone.climate.async_setup_entry",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.izone.config_flow.async_start_discovery_service"
    ) as start_disco, patch(
        "homeassistant.components.izone.async_start_discovery_service",
        return_value=None,
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    mock_setup.assert_called_once()
