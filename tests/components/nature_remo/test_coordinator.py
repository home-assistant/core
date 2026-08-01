"""Tests for the Nature Remo coordinator."""

from datetime import datetime
from unittest.mock import AsyncMock

from aionatureremo import (
    NatureRemoAuthError,
    NatureRemoConnectionError,
    NatureRemoRateLimitError,
)
import pytest

from homeassistant.components.nature_remo.coordinator import NatureRemoCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> NatureRemoCoordinator:
    """Build a coordinator wired to the mocked client."""
    mock_config_entry.add_to_hass(hass)
    return NatureRemoCoordinator(hass, mock_config_entry, mock_client)


async def test_update_success(coordinator: NatureRemoCoordinator) -> None:
    """A successful update indexes devices and appliances by id."""
    data = await coordinator._async_update_data()

    assert set(data.devices) == {"device-remo3-1", "device-mini-1", "device-remoe-1"}
    assert set(data.appliances) == {
        "appliance-ac-1",
        "appliance-ac-2",
        "appliance-tv-1",
        "appliance-light-1",
        "appliance-ir-1",
        "appliance-meter-1",
        "appliance-floorheater-1",
        "appliance-projector-1",
    }


async def test_auth_error_raises_config_entry_auth_failed(
    coordinator: NatureRemoCoordinator, mock_client: AsyncMock
) -> None:
    """A 401 from the API triggers reauth."""
    mock_client.get_devices.side_effect = NatureRemoAuthError(401, "bad token")

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "auth_failed"


async def test_rate_limit_raises_update_failed_with_reset(
    coordinator: NatureRemoCoordinator, mock_client: AsyncMock
) -> None:
    """A 429 names when requests are accepted again and defers the next poll."""
    reset = int(dt_util.utcnow().timestamp()) + 120
    mock_client.get_appliances.side_effect = NatureRemoRateLimitError(
        429, "limited", reset=reset
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "update_rate_limited"
    assert exc_info.value.translation_placeholders is not None
    reported = exc_info.value.translation_placeholders["reset"]
    assert datetime.fromisoformat(reported) == dt_util.utc_from_timestamp(reset)
    assert exc_info.value.retry_after is not None
    assert 0 < exc_info.value.retry_after <= 120


async def test_rate_limit_with_a_past_reset_keeps_the_normal_interval(
    coordinator: NatureRemoCoordinator, mock_client: AsyncMock
) -> None:
    """A reset already behind us must not schedule an immediate retry.

    ``retry_after`` becomes the next update interval verbatim, so a zero
    or negative delay would poll in a tight loop.
    """
    mock_client.get_appliances.side_effect = NatureRemoRateLimitError(
        429, "limited", reset=1752825600
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "update_rate_limited"
    assert exc_info.value.retry_after is None


async def test_rate_limit_without_reset_raises_update_failed(
    coordinator: NatureRemoCoordinator, mock_client: AsyncMock
) -> None:
    """A 429 with no reset header degrades to a plain update failure.

    "resets at epoch None" must never reach the UI; without a known reset
    the rate-limit error is just another failed poll.
    """
    mock_client.get_appliances.side_effect = NatureRemoRateLimitError(
        429, "limited", reset=None
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "update_failed"
    assert exc_info.value.translation_placeholders == {"error": "HTTP 429: limited"}


async def test_connection_error_raises_update_failed(
    coordinator: NatureRemoCoordinator, mock_client: AsyncMock
) -> None:
    """Network trouble becomes UpdateFailed."""
    mock_client.get_devices.side_effect = NatureRemoConnectionError("refused")

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "update_failed"
    assert exc_info.value.translation_placeholders == {"error": "refused"}
