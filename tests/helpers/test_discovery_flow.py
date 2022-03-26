"""Test the discovery flow helper."""

from unittest.mock import AsyncMock, call, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import EVENT_HOMEASSISTANT_STARTED, CoreState
from homeassistant.helpers import discovery_flow


@pytest.fixture
def mock_flow_init(hass):
    """Mock hass.config_entries.flow.async_init."""
    with patch.object(
        hass.config_entries.flow, "async_init", return_value=AsyncMock()
    ) as mock_init:
        yield mock_init


async def test_async_create_flow(hass, mock_flow_init):
    """Test we can create a flow."""
    discovery_flow.async_create_flow(
        hass,
        "hue",
        {"source": config_entries.SOURCE_HOMEKIT},
        {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
    )
    assert mock_flow_init.mock_calls == [
        call(
            "hue",
            context={"source": "homekit"},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    ]


async def test_async_create_flow_deferred_until_started(hass, mock_flow_init):
    """Test flows are deferred until started."""
    hass.state = CoreState.stopped
    discovery_flow.async_create_flow(
        hass,
        "hue",
        {"source": config_entries.SOURCE_HOMEKIT},
        {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
    )
    assert not mock_flow_init.mock_calls
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert mock_flow_init.mock_calls == [
        call(
            "hue",
            context={"source": "homekit"},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    ]


async def test_async_create_flow_checks_existing_flows(hass, mock_flow_init):
    """Test existing flows prevent an identical one from being creates."""
    with patch(
        "homeassistant.data_entry_flow.FlowManager.async_has_matching_flow",
        return_value=True,
    ):
        discovery_flow.async_create_flow(
            hass,
            "hue",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        assert not mock_flow_init.mock_calls
