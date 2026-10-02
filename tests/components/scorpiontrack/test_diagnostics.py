"""Test ScorpionTrack diagnostics."""

from dataclasses import replace
from unittest.mock import AsyncMock

from pyscorpiontrack import ScorpionTrackConnectionError, ScorpionTrackShare
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scorpiontrack.const import CONF_SHARE_TOKEN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.freeze_time("2026-09-07T12:00:00Z")


@pytest.mark.parametrize(
    "update_error",
    [
        pytest.param(None, id="successful_update"),
        pytest.param(
            ScorpionTrackConnectionError("Failed request for canonical-token"),
            id="failed_update",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    mock_share: ScorpionTrackShare,
    snapshot: SnapshotAssertion,
    update_error: ScorpionTrackConnectionError | None,
) -> None:
    """Test redaction for every vehicle without fetching or changing cached data."""
    vehicle = mock_share.vehicles[0]
    share = replace(
        mock_share,
        vehicles=(vehicle, replace(vehicle, id=2, registration="EF34 GHI")),
    )
    mock_scorpiontrack_client.async_get_share.return_value = share
    await setup_integration(hass, mock_config_entry)
    mock_scorpiontrack_client.async_get_share.side_effect = update_error
    await mock_config_entry.runtime_data.async_refresh()
    mock_scorpiontrack_client.async_get_share.reset_mock()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot
    mock_scorpiontrack_client.async_get_share.assert_not_awaited()
    assert mock_config_entry.runtime_data.data == share
    assert mock_config_entry.data[CONF_SHARE_TOKEN] == "canonical-token"


async def test_diagnostics_missing_position(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    mock_share: ScorpionTrackShare,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when a vehicle has no position data."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(
                vehicle,
                position=replace(
                    vehicle.position,
                    latitude=None,
                    longitude=None,
                    timestamp=None,
                    speed_kmh=None,
                    ignition=None,
                    bearing=None,
                    address=None,
                ),
                status="unknown",
            ),
        ),
    )
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
