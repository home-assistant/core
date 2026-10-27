"""Test the ecosmart integration setup and unload."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aioecosmart import (
    EcosmartAuthError,
    EcosmartConnectionError,
    EcosmartError,
    EcosmartRateLimitError,
    IcpScope,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ecosmart.const import SPOT_SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration
from .conftest import TEST_POC, load_identity


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry loads, polls the spot price, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ecosmart_client.me.assert_awaited_once()
    mock_ecosmart_client.spot.assert_awaited_once_with(TEST_POC)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_pocs_are_deduplicated(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test two connection points on one grid exit point cost one request."""
    identity = load_identity()
    second_icp = replace(identity.allowed_icps[0], icp="0000123456AB124")
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], second_icp]
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ecosmart_client.spot.assert_awaited_once_with(TEST_POC)
    # Two ICPs, one grid exit point, two entities.
    assert len(hass.states.async_entity_ids("sensor")) == 2


async def test_two_pocs_are_both_fetched(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection points on different grid exit points are both polled."""
    identity = load_identity()
    other = IcpScope(
        icp="0000123456AB125",
        poc="ISL0661",
        network="OTPO",
        price_category_code="RSUC",
    )
    mock_ecosmart_client.me.return_value = replace(
        identity, allowed_icps=[identity.allowed_icps[0], other]
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_ecosmart_client.spot.await_count == 2


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_translation_key"),
    [
        (EcosmartAuthError("nope"), ConfigEntryState.SETUP_ERROR, "invalid_auth"),
        (
            EcosmartConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
        ),
        (EcosmartError("weird"), ConfigEntryState.SETUP_RETRY, "cannot_connect"),
    ],
)
async def test_identity_failures(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_translation_key: str,
) -> None:
    """Test the test-before-setup call decides how the entry fails."""
    mock_ecosmart_client.me.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == expected_translation_key


@pytest.mark.parametrize("failing_call", ["me", "spot"])
async def test_rejected_key_asks_for_a_new_one(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    failing_call: str,
) -> None:
    """Test a rejected key starts the reauth flow for this entry."""
    getattr(mock_ecosmart_client, failing_call).side_effect = EcosmartAuthError("nope")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize("failing_call", ["me", "spot"])
@pytest.mark.parametrize(
    ("side_effect", "expected_delay"),
    [
        (EcosmartRateLimitError("slow down", retry_after=30), 30),
        # No Retry-After header: back off for our own poll interval instead.
        (EcosmartRateLimitError("slow down"), 300),
    ],
)
async def test_setup_rate_limit_waits_for_the_server(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    failing_call: str,
    side_effect: Exception,
    expected_delay: int,
) -> None:
    """Test a rate limit during setup retries after the server's delay.

    Both setup calls are covered: the identity lookup and the first price
    fetch. Without the delay Home Assistant would retry after about five
    seconds, into a key that is still out of budget.
    """
    failing = getattr(mock_ecosmart_client, failing_call)
    failing.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "rate_limited"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "retry_after": str(expected_delay)
    }

    failing.side_effect = None
    freezer.tick(timedelta(seconds=expected_delay - 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (EcosmartAuthError("nope"), ConfigEntryState.SETUP_ERROR),
        (EcosmartConnectionError("offline"), ConfigEntryState.SETUP_RETRY),
        (
            EcosmartRateLimitError("slow down", retry_after=30),
            ConfigEntryState.SETUP_RETRY,
        ),
        (EcosmartRateLimitError("slow down"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_first_refresh_failures(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the first price fetch maps each API failure to the right state."""
    mock_ecosmart_client.spot.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_later_rate_limit_without_header_uses_scan_interval(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a later 429 with no Retry-After falls back to our poll cadence."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None

    mock_ecosmart_client.spot.side_effect = EcosmartRateLimitError("slow down")

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.translation_key == "rate_limited"
    assert err.value.retry_after == int(SPOT_SCAN_INTERVAL.total_seconds())
    assert err.value.translation_placeholders == {
        "retry_after": str(int(SPOT_SCAN_INTERVAL.total_seconds()))
    }


async def test_rate_limit_retry_after_moves_the_next_poll(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the server's Retry-After decides when we come back, not our cadence."""
    await setup_integration(hass, mock_config_entry)
    mock_ecosmart_client.spot.reset_mock()

    mock_ecosmart_client.spot.side_effect = EcosmartRateLimitError(
        "slow down", retry_after=30
    )
    freezer.tick(SPOT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_ecosmart_client.spot.await_count == 1

    # Thirty seconds is well short of the five-minute cadence, so a second
    # fetch here can only mean the header was honoured.
    mock_ecosmart_client.spot.side_effect = None
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_ecosmart_client.spot.await_count == 2
