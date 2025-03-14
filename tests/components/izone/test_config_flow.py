"""Tests for iZone."""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.izone.const import DISPATCH_CONTROLLER_DISCOVERED, IZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_send


@pytest.fixture
def mock_disco() -> Mock:
    """Mock discovery service."""
    disco = Mock()
    disco.pi_disco = Mock()
    disco.pi_disco.controllers = {}
    return disco


def _mock_start_discovery(hass: HomeAssistant, mock_disco: Mock) -> Callable[..., Mock]:
    def do_disovered(*args: Any) -> Mock:
        async_dispatcher_send(hass, DISPATCH_CONTROLLER_DISCOVERED, True)
        return mock_disco

    return do_disovered


async def test_not_found(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test not finding iZone controller."""

    with (
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.config_flow.async_stop_discovery_service",
            return_value=None,
        ) as stop_disco,
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

    stop_disco.assert_called_once()


async def test_found(hass: HomeAssistant, mock_disco: Mock) -> None:
    """Test not finding iZone controller."""
    mock_disco.pi_disco.controllers["blah"] = object()

    with (
        patch(
            "homeassistant.components.izone.climate.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.izone.config_flow.async_start_discovery_service"
        ) as start_disco,
        patch(
            "homeassistant.components.izone.async_start_discovery_service",
            return_value=None,
        ),
    ):
        start_disco.side_effect = _mock_start_discovery(hass, mock_disco)
        result = await hass.config_entries.flow.async_init(
            IZONE, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    mock_setup.assert_called_once()
