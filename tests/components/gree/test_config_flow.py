"""Tests for the Gree Integration."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN
from homeassistant.core import HomeAssistant

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
            GREE_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = []

        result = await hass.config_entries.flow.async_init(
            GREE_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.ABORT

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0
