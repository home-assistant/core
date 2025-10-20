"""Tests for the Yardian coordinator."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pyyardian import NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN
from homeassistant.components.yardian.coordinator import (
    YardianCombinedState,
    YardianUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_coordinator_combines_state(hass: HomeAssistant) -> None:
    """Coordinator returns combined state from device and operation info."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "access_token": "token",
            "yid": "yardian-1",
            "model": "PRO",
        },
        title="Yardian",
        unique_id="yardian-1",
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.fetch_device_state.return_value = SimpleNamespace(
        zones=[["Zone 1", 1]],
        active_zones={0},
    )
    client.fetch_oper_info.return_value = {"iStandby": 1}

    with patch(
        "homeassistant.components.yardian.AsyncYardianClient", return_value=client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(coordinator, YardianUpdateCoordinator)

    state = coordinator.data
    assert isinstance(state, YardianCombinedState)
    assert state.zones == [["Zone 1", 1]]
    assert state.active_zones == {0}
    assert state.oper_info["iStandby"] == 1


@pytest.mark.asyncio
async def test_coordinator_raises_auth_failed(hass: HomeAssistant) -> None:
    """Coordinator raises ConfigEntryAuthFailed on invalid auth."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "access_token": "token",
            "yid": "yardian-1",
            "model": "PRO",
        },
        title="Yardian",
        unique_id="yardian-1",
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.fetch_device_state.side_effect = NotAuthorizedException

    with (
        patch(
            "homeassistant.components.yardian.AsyncYardianClient", return_value=client
        ),
        patch.object(
            hass.config_entries.flow,
            "async_init",
            AsyncMock(
                return_value={"type": "abort", "reason": "reauth_not_supported"}
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.data.get(DOMAIN, {}).get(entry.entry_id) is None
