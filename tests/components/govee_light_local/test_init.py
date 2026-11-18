"""Tests init for the Govee Local API integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import (
    CLEANUP_TIMEOUT,
    CLEANUP_WAIT_TIMEOUT,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import DISABLED_NETWORK_ADAPTERS, setup_light


async def test_setup_without_listening_addresses(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup is retried when no enabled adapter has an IPv4 address."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.network.async_get_adapters",
        return_value=DISABLED_NETWORK_ADAPTERS,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert (
        config_entry.reason
        == "No enabled network adapter has an IPv4 address to listen on"
    )
    mock_govee_api.start.assert_not_awaited()


@pytest.mark.usefixtures("mock_network_adapters")
async def test_unload_releases_port(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test unloading waits for the controller to release the listening port."""

    entry, _ = await setup_light(hass, mock_govee_api)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    mock_govee_api.cleanup.assert_called_once_with(timeout=CLEANUP_TIMEOUT)


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_waits_for_delayed_cleanup(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading keeps waiting for a cleanup that completes late."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)
    assert not unload_task.done()

    # Two seconds in: inside the cleanup wait window, so unload is still pending.
    freezer.tick(2)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not unload_task.done()

    mock_govee_api.cleanup.return_value.set()
    assert await unload_task

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port" not in caplog.text


@pytest.mark.usefixtures("mock_network_adapters", "mock_stuck_cleanup")
async def test_unload_warns_when_port_not_released(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a controller that never closes its sockets does not wedge the unload."""

    entry, _ = await setup_light(hass, mock_govee_api)

    unload_task = hass.async_create_task(
        hass.config_entries.async_unload(entry.entry_id)
    )
    await asyncio.sleep(0)

    freezer.tick(CLEANUP_WAIT_TIMEOUT + 1)
    await asyncio.sleep(0)
    assert await unload_task
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert "Timed out waiting for port 4002 to be released" in caplog.text
