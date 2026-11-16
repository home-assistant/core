"""Tests for the Gree Integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.gree.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import FakeDiscovery

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_sets_up_climate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Gree Climate"
        assert result["data"] == {}
        assert result["result"].unique_id == DOMAIN

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup can succeed after no devices were initially discovered."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0

        discovery.return_value = FakeDiscovery()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Gree Climate"
        assert result["data"] == {}
        assert result["result"].unique_id == DOMAIN

        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()
