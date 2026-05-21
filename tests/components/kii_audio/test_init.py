"""Tests for the Kii Audio integration setup."""

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.kii_audio import async_unload_entry
from homeassistant.components.kii_audio.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import SYSTEM_ID, make_zone

from tests.common import MockConfigEntry


async def _async_wait_ready(coordinator: Any) -> None:
    """Set initial Kii Audio data after the coordinator is ready."""
    coordinator.async_set_updated_data(
        {"systemName": "Kii System", "zones": [make_zone()]}
    )


def _mock_config_entry(**data: object) -> MockConfigEntry:
    """Return a Kii Audio config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Kii Audio",
        data={CONF_HOST: "192.0.2.1", CONF_SYSTEM_ID: SYSTEM_ID, **data},
        unique_id=SYSTEM_ID,
    )


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=_async_wait_ready,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as mock_forward_setups,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    mock_forward_setups.assert_awaited_once()


async def test_setup_entry_removes_stale_port(hass: HomeAssistant) -> None:
    """Test stale port data is removed during setup."""
    entry = _mock_config_entry(**{CONF_PORT: 9000})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=_async_wait_ready,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert CONF_PORT not in entry.data


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test setup retries when initial system information is unavailable."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=AsyncMock(side_effect=TimeoutError),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_stop",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_stop.assert_awaited_once()


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry stops the coordinator."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=_async_wait_ready,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_stop",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_stop.assert_awaited_once()


async def test_unload_entry_keeps_coordinator_running_when_platform_unload_fails(
    hass: HomeAssistant,
) -> None:
    """Test failed platform unload keeps the coordinator running."""
    entry = _mock_config_entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_start",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_wait_ready",
            new=_async_wait_ready,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "homeassistant.components.kii_audio.coordinator.KiiAudioCoordinator.async_stop",
            new=AsyncMock(),
        ) as mock_stop,
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.FAILED_UNLOAD
    mock_stop.assert_not_awaited()


async def test_unload_entry_without_runtime_data(hass: HomeAssistant) -> None:
    """Test unloading before runtime data is available is a no-op."""
    entry = _mock_config_entry()
    entry.runtime_data = None  # type: ignore[assignment]

    assert await async_unload_entry(hass, entry)
