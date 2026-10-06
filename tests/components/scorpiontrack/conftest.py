"""Test fixtures for the ScorpionTrack integration."""

from collections.abc import Iterator
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackPosition,
    ScorpionTrackShare,
    ScorpionTrackVehicle,
)
import pytest

from homeassistant.components.scorpiontrack.const import CONF_SHARE_TOKEN, DOMAIN
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_share() -> ScorpionTrackShare:
    """Return a representative ScorpionTrack share."""
    now = dt_util.utcnow()
    return ScorpionTrackShare(
        id=101,
        token="canonical-token",
        title="Family Cars",
        owner_name="Ashby Herbert",
        distance_units="miles",
        created_at=now - timedelta(days=3),
        expires_at=now + timedelta(days=28),
        vehicles=(
            ScorpionTrackVehicle(
                id=1,
                name="Golf R",
                registration="AB12 CDE",
                make="Volkswagen",
                model="Golf R",
                position=ScorpionTrackPosition(
                    latitude=51.5074,
                    longitude=-0.1278,
                    timestamp=now - timedelta(days=2),
                    speed_kmh=48.3,
                    ignition=True,
                    bearing=182.0,
                    address="Westminster, London",
                ),
                status="Moving",
            ),
        ),
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Family Cars",
        data={CONF_SHARE_TOKEN: "canonical-token"},
        unique_id="101",
        entry_id="01SCORPIONTRACK_TEST_ENTRY",
    )


@pytest.fixture
def mock_scorpiontrack_client_class() -> Iterator[MagicMock]:
    """Mock the ScorpionTrack client constructor."""
    with (
        patch(
            "homeassistant.components.scorpiontrack.ScorpionTrackClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient",
            new=mock_client,
        ),
    ):
        mock_client.extract_token.side_effect = ScorpionTrackClient.extract_token
        yield mock_client


@pytest.fixture(autouse=True)
def mock_scorpiontrack_client(
    mock_scorpiontrack_client_class: MagicMock,
    mock_share: ScorpionTrackShare,
) -> AsyncMock:
    """Return the mocked ScorpionTrack client."""
    client = mock_scorpiontrack_client_class.return_value
    client.token = "canonical-token"
    client.async_get_share.return_value = mock_share
    return client
