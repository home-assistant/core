"""Tests for the Uptime Kuma integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator
from pythonkuma import (
    UptimeKumaAuthenticationException,
    UptimeKumaException,
    UptimeKumaParseException,
    UptimeKumaVersion,
)

from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (UptimeKumaAuthenticationException, ConfigEntryState.SETUP_ERROR),
        (UptimeKumaException, ConfigEntryState.SETUP_RETRY),
        (UptimeKumaParseException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready."""

    mock_pythonkuma.metrics.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


async def test_config_entry_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
) -> None:
    """Test config entry not ready."""

    mock_pythonkuma.version = UptimeKumaVersion(
        version="1.23.16", major="1", minor="23", patch="16"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_config_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
) -> None:
    """Test config entry auth error starts reauth flow."""

    mock_pythonkuma.metrics.side_effect = UptimeKumaAuthenticationException
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_remove_stale_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can remove a device that is not in the coordinator data."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456789_1"), config_entry.entry_id
    )

    config_entry.runtime_data.data.pop(1)
    response = await ws_client.remove_device(device_entry.id)

    assert response["success"]
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "123456789_1"), config_entry.entry_id
        )
        is None
    )


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_remove_current_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we cannot remove a device if it is still active."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456789_1"), config_entry.entry_id
    )

    response = await ws_client.remove_device(device_entry.id)

    assert response["success"] is False
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456789_1"), config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_remove_entry_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we cannot remove the device with the update entity."""
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456789"), config_entry.entry_id
    )

    response = await ws_client.remove_device(device_entry.id)

    assert response["success"] is False
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456789"), config_entry.entry_id
    )


@pytest.mark.usefixtures("mock_pythonkuma")
async def test_device_info_sw_version_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_pythonkuma: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device info is updated on Uptime Kuma version change."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        device_entry := device_registry.async_get_device_by_identifier(
            (DOMAIN, "123456789_1"), config_entry.entry_id
        )
    )

    assert device_entry.sw_version == "2.0.0"

    mock_pythonkuma.version = UptimeKumaVersion(
        version="2.5.6", major="2", minor="5", patch="6"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_entry := device_registry.async_get_device_by_identifier(
            (DOMAIN, "123456789_1"), config_entry.entry_id
        )
    )

    assert device_entry.sw_version == "2.5.6"
