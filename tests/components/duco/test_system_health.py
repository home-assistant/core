"""Tests for Duco system health."""

from unittest.mock import AsyncMock, Mock

from duco.exceptions import DucoConnectionError

from homeassistant.components.duco.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_system_health_info


async def test_system_health_single_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test system health for a single loaded entry."""
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert await info["write_requests_remaining"] == 100


async def test_system_health_single_entry_quota_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test system health reports unreachable when quota retrieval fails."""
    mock_duco_client.async_get_write_req_remaining.side_effect = DucoConnectionError

    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert await info["write_requests_remaining"] == {
        "type": "failed",
        "error": "unreachable",
    }


async def test_system_health_no_loaded_entries(hass: HomeAssistant) -> None:
    """Test system health without loaded entries."""
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    assert await get_system_health_info(hass, DOMAIN) == {}


async def test_system_health_multiple_entries(hass: HomeAssistant) -> None:
    """Test system health omits per-device quota for multiple loaded entries."""
    hass.config.components.add(DOMAIN)
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    first_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        state=ConfigEntryState.LOADED,
    )
    first_entry.add_to_hass(hass)
    first_entry.runtime_data = Mock(
        client=Mock(async_get_write_req_remaining=AsyncMock(return_value=100))
    )

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="11:22:33:44:55:66",
        state=ConfigEntryState.LOADED,
    )
    second_entry.add_to_hass(hass)
    second_entry.runtime_data = Mock(
        client=Mock(async_get_write_req_remaining=AsyncMock(return_value=200))
    )

    assert await get_system_health_info(hass, DOMAIN) == {}
