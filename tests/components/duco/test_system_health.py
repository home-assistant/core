"""Tests for Duco system health."""

from unittest.mock import AsyncMock

from duco_connectivity.exceptions import DucoConnectionError

from homeassistant.components.duco.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration

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
    mock_duco_client.async_get_write_requests_remaining.side_effect = (
        DucoConnectionError
    )

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


async def test_system_health_multiple_loaded_entries(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test system health reports quota per loaded Duco box."""
    second_entry = MockConfigEntry(
        title="SECOND_BOX",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.101"},
        unique_id="aa:bb:cc:dd:ee:00",
    )
    await setup_integration(hass, second_entry)
    mock_duco_client.async_get_write_requests_remaining.side_effect = [100, 75]

    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["loaded_entries"] == 2
    assert await info["write_requests_remaining (SILENT_CONNECT: 192.168.1.100)"] == 100
    assert await info["write_requests_remaining (SECOND_BOX: 192.168.1.101)"] == 75
