"""Tests for TFA.me: test of __init__.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tfa_me import (
    async_unload_entry,
    get_instances,
    get_running_instances,
)
from homeassistant.components.tfa_me.const import CONF_MULTIPLE_ENTITIES, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry, async_capture_events


def mock_config_entryX() -> MockConfigEntry:
    """Fixture for a MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_MULTIPLE_ENTITIES: True,
        },
        entry_id="1234",
        unique_id="unique_1234",
    )


@pytest.mark.asyncio
async def test_full_entry_setup(hass: HomeAssistant) -> None:
    """Test full setup of the integration."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # assert mock_config_entry.entry_id in hass.data[DOMAIN]
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unload of the integration."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_get_instances_and_running(
    hass: HomeAssistant,
) -> None:
    """Test get_instances and get_running_instances."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"

    instances = await get_instances(hass)
    running = await get_running_instances(hass)

    assert mock_config_entry in instances
    assert mock_config_entry in running


@pytest.mark.asyncio
async def test_manual_refresh_service(hass: HomeAssistant) -> None:
    """Test manual refresh service."""

    # 1) Create ConfigEntry
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    # 2) Set up integration
    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # 3) Get coordinator and mock refresh-method
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.async_request_refresh = AsyncMock()

    # 4) Capture events
    events = async_capture_events(hass, "tfa_me_manual_refresh")

    # 5) Set service name
    service_name = "tfa_me_manual_refresh"

    # 6) Call service
    await hass.services.async_call(
        DOMAIN, service_name, {"host": "127.0.0.1"}, blocking=True
    )
    await hass.async_block_till_done()

    # 7) Asserts: Refresh awaited + event seen
    coordinator.async_request_refresh.assert_awaited_once()
    assert len(events) == 1
    assert events[0].data == {"result": "ok", "host": "127.0.0.1"}

    # 8) Call service with wrong IP
    with pytest.raises(HomeAssistantError, match="No coordinator for host '127.0.0.2'"):
        await hass.services.async_call(
            DOMAIN, service_name, {"host": "127.0.0.2"}, blocking=True
        )
