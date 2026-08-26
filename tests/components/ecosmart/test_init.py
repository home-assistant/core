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

from homeassistant.components.ecosmart.const import SPOT_SCAN_INTERVAL
from homeassistant.components.ecosmart.coordinator import EcosmartCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration
from .conftest import TEST_POC, load_identity

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry loads, polls both planes, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ecosmart_client.me.assert_awaited_once()
    mock_ecosmart_client.spot.assert_awaited_once_with(TEST_POC)
    mock_ecosmart_client.forecast.assert_awaited_once_with(TEST_POC, hours=48)

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
    # Two ICPs, one grid exit point, four entities.
    assert len(hass.states.async_entity_ids("sensor")) == 4


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


@pytest.mark.parametrize(
    "side_effect",
    [
        EcosmartRateLimitError("slow down", retry_after=30),
        # No Retry-After header either — setup must not invent a delay claim.
        EcosmartRateLimitError("slow down"),
    ],
)
async def test_identity_rate_limit_is_reported_as_such(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test a spent budget is not reported as a connection failure.

    ConfigEntryNotReady has no retry_after support, so the setup path must
    use a message that does not claim a delay Home Assistant will not honour.
    """
    mock_ecosmart_client.me.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "rate_limited_setup"
    placeholders = mock_config_entry.error_reason_translation_placeholders or {}
    assert "retry_after" not in placeholders
    # The rendered reason must not claim a number of seconds either.
    reason = str(mock_config_entry.reason or "")
    assert not any(ch.isdigit() for ch in reason)


async def test_first_refresh_rate_limit_omits_retry_after(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an initial 429 does not claim a delay HA will ignore.

    async_config_entry_first_refresh ignores UpdateFailed.retry_after and
    converts the failure to a normal config-entry retry (~5s), so the
    setup-time path must not pass or advertise a server delay.
    """
    mock_config_entry.add_to_hass(hass)
    coordinator: EcosmartCoordinator = EcosmartCoordinator(
        hass,
        mock_config_entry,
        [TEST_POC],
        name="spot price",
        update_interval=SPOT_SCAN_INTERVAL,
        fetch=mock_ecosmart_client.spot,
    )
    assert coordinator.data is None
    mock_ecosmart_client.spot.side_effect = EcosmartRateLimitError(
        "slow down", retry_after=30
    )

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.translation_key == "rate_limited_setup"
    assert err.value.retry_after is None
    assert not err.value.translation_placeholders


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
    coordinator = mock_config_entry.runtime_data.spot_coordinator
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
