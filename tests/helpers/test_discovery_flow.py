"""Test the discovery flow helper."""
from unittest.mock import AsyncMock, call, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import EVENT_HOMEASSISTANT_STARTED, CoreState, HomeAssistant
from homeassistant.helpers import discovery_flow


@pytest.fixture
def mock_flow_init(hass):
    """Mock hass.config_entries.flow.async_init."""
    with patch.object(
        hass.config_entries.flow, "async_init", return_value=AsyncMock()
    ) as mock_init:
        yield mock_init


async def test_async_create_flow(hass: HomeAssistant, mock_flow_init) -> None:
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


async def test_async_create_flow_deferred_until_started(
    hass: HomeAssistant, mock_flow_init
) -> None:
    """Test flows are deferred until started."""
    hass.set_state(CoreState.stopped)
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


async def test_async_create_flow_checks_existing_flows_after_startup(
    hass: HomeAssistant, mock_flow_init
) -> None:
    """Test existing flows prevent an identical ones from being after startup."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
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


async def test_async_create_flow_checks_existing_flows_before_startup(
    hass: HomeAssistant, mock_flow_init
) -> None:
    """Test existing flows prevent an identical ones from being created before startup."""
    hass.set_state(CoreState.stopped)
    for _ in range(2):
        discovery_flow.async_create_flow(
            hass,
            "hue",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert mock_flow_init.mock_calls == [
        call(
            "hue",
            context={"source": "homekit"},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    ]


async def test_async_create_flow_does_nothing_after_stop(
    hass: HomeAssistant, mock_flow_init
) -> None:
    """Test we no longer create flows when hass is stopping."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    hass.set_state(CoreState.stopping)
    mock_flow_init.reset_mock()
    discovery_flow.async_create_flow(
        hass,
        "hue",
        {"source": config_entries.SOURCE_HOMEKIT},
        {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
    )
    assert len(mock_flow_init.mock_calls) == 0
