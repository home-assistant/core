"""Define fixtures available for all tests."""
from pytest import fixture

from . import MOCK_AREAS, MOCK_ZONES

from tests.async_mock import MagicMock, patch


@fixture
def ultrasync_api(hass):
    """Mock UltraSync for easier testing."""

    with patch("ultrasync.UltraSync") as mock_api:
        instance = mock_api.return_value
        instance.login = MagicMock(return_value=True)
        instance.details = MagicMock(
            return_value={
                "areas": MOCK_AREAS,
                "zones": MOCK_ZONES,
            }
        )
        instance.areas = MagicMock(return_value=list(MOCK_AREAS))
        instance.zones = MagicMock(return_value=list(MOCK_ZONES))
        yield mock_api
