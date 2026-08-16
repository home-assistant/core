"""Common fixtures for the Hydro-Québec Peak Events tests."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from hydropeak_opendata import PeakEvent
import pytest

from homeassistant.components.hydroquebec_peak.const import CONF_OFFER, DOMAIN

from tests.common import MockConfigEntry

TEST_OFFER = "Credit hivernal Residentiel (CPC-D)"
OTHER_OFFER = "Flex Residentiel (TPC-DPC)"

EST = timezone(timedelta(hours=-5))

TEST_EVENTS = (
    PeakEvent(
        offer=TEST_OFFER,
        start=datetime(2026, 1, 9, 6, 0, tzinfo=EST),
        end=datetime(2026, 1, 9, 9, 0, tzinfo=EST),
        period="AM",
        sector="Residentiel",
    ),
    PeakEvent(
        offer=TEST_OFFER,
        start=datetime(2026, 1, 9, 16, 0, tzinfo=EST),
        end=datetime(2026, 1, 9, 20, 0, tzinfo=EST),
        period="PM",
        sector="Residentiel",
    ),
    PeakEvent(
        offer=TEST_OFFER,
        start=datetime(2026, 1, 10, 6, 0, tzinfo=EST),
        end=datetime(2026, 1, 10, 9, 0, tzinfo=EST),
        period="AM",
        sector="Residentiel",
    ),
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hydroquebec_peak.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_OFFER,
        domain=DOMAIN,
        data={CONF_OFFER: TEST_OFFER},
        unique_id=TEST_OFFER,
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Return a mocked OpenDataClient."""
    with (
        patch(
            "homeassistant.components.hydroquebec_peak.coordinator.OpenDataClient",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.hydroquebec_peak.config_flow.OpenDataClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.get_offer_labels = AsyncMock(
            return_value={TEST_OFFER: TEST_OFFER, OTHER_OFFER: OTHER_OFFER}
        )
        client.get_events = AsyncMock(return_value=TEST_EVENTS)
        yield client
