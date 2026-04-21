"""Test fixtures for the ScorpionTrack integration."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from pyscorpiontrack import (
    ScorpionTrackPosition,
    ScorpionTrackShare,
    ScorpionTrackVehicle,
)
import pytest

from homeassistant.components.scorpiontrack.const import CONF_SHARE_TOKEN, DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_share() -> ScorpionTrackShare:
    """Return a representative ScorpionTrack share."""
    return ScorpionTrackShare(
        id=101,
        token="canonical-token",
        title="Family Cars",
        owner_name="Ashby Herbert",
        distance_units="miles",
        created_at=datetime(2026, 4, 20, 19, 0, tzinfo=UTC),
        expires_at=datetime(2026, 5, 20, 19, 0, tzinfo=UTC),
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
                    timestamp=datetime(2026, 4, 21, 7, 0, tzinfo=UTC),
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


@pytest.fixture(autouse=True)
def mock_scorpiontrack_client(mock_share: ScorpionTrackShare) -> Generator[AsyncMock]:
    """Mock the ScorpionTrack client."""
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
        client = mock_client.return_value
        client.token = "canonical-token"
        client.async_get_share.return_value = mock_share
        yield client


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore known core translation gaps only for tests that set up platforms."""
    if request.node.originalname in {
        "test_user_flow_creates_entry",
        "test_setup_entry",
        "test_device_tracker_state",
        "test_device_is_registered",
        "test_removed_vehicle_becomes_unavailable",
    }:
        return [
            "component.device_tracker.services.see.",
            "component.zone.services.reload.",
        ]

    return []
