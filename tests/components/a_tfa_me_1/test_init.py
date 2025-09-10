"""Tests for TFA.me: test of __init__.py."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.a_tfa_me_1 import (
    async_unload_entry,
    async_update_listener,
    get_instances,
    get_running_instances,
)
from homeassistant.components.a_tfa_me_1.const import (
    CONF_INTERVAL,
    CONF_MULTIPLE_ENTITIES,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def mock_config_entryX() -> MockConfigEntry:
    """Fixture for a MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_INTERVAL: 30,
            CONF_MULTIPLE_ENTITIES: True,
        },
        options={CONF_INTERVAL: 33},
        entry_id="1234",
        unique_id="unique_1234",
    )


@pytest.mark.asyncio
async def test_full_entry_setup(hass: HomeAssistant) -> None:
    """Test full setup of the integration."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.a_tfa_me_1.TFAmeDataCoordinator.async_config_entry_first_refresh",
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
        "homeassistant.components.a_tfa_me_1.TFAmeDataCoordinator.async_config_entry_first_refresh",
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
async def test_async_update_listener(hass: HomeAssistant) -> None:
    """Test update listener adjusts interval."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.a_tfa_me_1.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"

    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    coordinator.async_refresh = AsyncMock()

    # Change options
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_INTERVAL: 99},
    )
    await hass.async_block_till_done()
    await async_update_listener(hass, mock_config_entry)

    assert coordinator.update_interval == timedelta(seconds=99)
    coordinator.async_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_get_instances_and_running(
    hass: HomeAssistant,
) -> None:
    """Test get_instances and get_running_instances."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.a_tfa_me_1.TFAmeDataCoordinator.async_config_entry_first_refresh",
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
