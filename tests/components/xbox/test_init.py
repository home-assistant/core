"""Tests for the Xbox integration."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectTimeout, HTTPStatusError, ProtocolError
import pytest
from pythonxbox.api.provider.smartglass.models import SmartglassConsoleStatus

from homeassistant.components.xbox.const import DOMAIN
from homeassistant.components.xbox.coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    FAST_UPDATE_INTERVAL,
    XboxConfigEntry,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)


@pytest.mark.usefixtures("xbox_live_client")
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
    "exception",
    [ConnectTimeout, HTTPStatusError, ProtocolError],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test config entry not ready."""

    xbox_live_client.smartglass.get_console_list.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("xbox_live_client")
async def test_config_implementation_not_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test implementation not available."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xbox.coordinator.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exception", [ConnectTimeout, HTTPStatusError, ProtocolError])
@pytest.mark.parametrize(
    ("provider", "method"),
    [
        ("smartglass", "get_console_status"),
        ("catalog", "get_product_from_alternate_id"),
        ("people", "get_friends_by_xuid"),
        ("people", "get_friends_own"),
    ],
)
async def test_coordinator_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    exception: Exception,
    provider: str,
    method: str,
) -> None:
    """Test coordinator update failed."""

    provider = getattr(xbox_live_client, provider)
    getattr(provider, method).side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("xbox_live_client")
@pytest.mark.freeze_time("2025-11-11T00:00:00+00:00")
async def test_variable_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test variable data updates depending on console power state."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry: XboxConfigEntry | None = hass.config_entries.async_get_entry(
        config_entry.entry_id
    )
    assert entry
    # console is on, update_interval is set to fast polling interval
    assert entry.runtime_data.update_interval is FAST_UPDATE_INTERVAL

    xbox_live_client.smartglass.get_console_status.return_value = (
        SmartglassConsoleStatus(
            **await async_load_json_object_fixture(
                hass, "smartglass_console_status_off.json", DOMAIN
            )  # type: ignore[arg-type]
        )
    )

    freezer.tick(FAST_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # revert to default interval when console is off
    assert entry.runtime_data.update_interval is DEFAULT_UPDATE_INTERVAL
