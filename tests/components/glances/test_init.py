"""Tests for Glances integration."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from glances_api.exceptions import (
    GlancesApiAuthorizationError,
    GlancesApiConnectionError,
    GlancesApiNoDataAvailable,
)
import pytest

from homeassistant.components.glances.const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Glances is configured successfully."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "entry_state"),
    [
        (GlancesApiAuthorizationError, ConfigEntryState.SETUP_ERROR),
        (GlancesApiConnectionError, ConfigEntryState.SETUP_RETRY),
        (GlancesApiNoDataAvailable, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    error: Exception,
    entry_state: ConfigEntryState,
    mock_api: MagicMock,
) -> None:
    """Test Glances failed due to api error."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    mock_api.return_value.get_ha_sensor_data.side_effect = error
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is entry_state


async def test_update_error_includes_message(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_api: MagicMock,
) -> None:
    """Test that the underlying API error message is propagated to UpdateFailed."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    mock_api.return_value.get_ha_sensor_data.side_effect = GlancesApiConnectionError(
        "Connection to http://localhost:61209/api/4/all failed"
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "Connection to http://localhost:61209/api/4/all failed" in str(
        coordinator.last_exception
    )


async def test_dedicated_httpx_client_uses_timeout_and_is_cached(
    hass: HomeAssistant,
) -> None:
    """The integration's dedicated httpx client uses DEFAULT_TIMEOUT and is reused on reload."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.glances.create_async_httpx_client"
    ) as mock_create:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert mock_create.call_count == 1
        kwargs = mock_create.call_args.kwargs
        assert kwargs["timeout"] == DEFAULT_TIMEOUT
        assert kwargs["verify_ssl"] == MOCK_USER_INPUT["verify_ssl"]

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_create.call_count == 1


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Glances."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
