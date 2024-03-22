"""Tests for the LinkPlay integration config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture(name="mock_no_devices_controller")
def mock_no_devices_controller_fixture() -> MagicMock:
    """Mock controller."""
    controller = MagicMock()
    controller.discover_bridges = AsyncMock()
    controller.discover_bridges.return_value = []
    return controller


@pytest.fixture(name="mock_devices_controller")
def mock_devices_controller_fixture() -> MagicMock:
    """Mock controller."""
    controller = MagicMock()
    controller.discover_bridges = AsyncMock()
    controller.bridges = [AsyncMock(), AsyncMock()]
    return controller


@pytest.mark.enable_socket
async def test_not_found(
    hass: HomeAssistant, mock_no_devices_controller: MagicMock
) -> None:
    """Test not finding any LinkPlay bridges."""

    with patch(
        "homeassistant.components.linkplay.config_flow.LinkPlayController",
        return_value=mock_no_devices_controller,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    assert mock_no_devices_controller.discover_bridges.call_count == 1


@pytest.mark.enable_socket
async def test_devices_found(
    hass: HomeAssistant, mock_devices_controller: MagicMock
) -> None:
    """Test not finding any LinkPlay bridges."""

    with patch(
        "homeassistant.components.linkplay.config_flow.LinkPlayController",
        return_value=mock_devices_controller,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_devices_controller.discover_bridges.call_count == 1
