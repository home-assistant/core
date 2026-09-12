"""Fixtures for Axle Energy."""

from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aioaxlevpp import GridEvent
import pytest

from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_event() -> GridEvent:
    """A synthetic future export event."""
    return GridEvent(
        start=datetime(2026, 9, 11, 17, tzinfo=UTC),
        end=datetime(2026, 9, 11, 18, tzinfo=UTC),
        direction="export",
        updated_at=datetime(2026, 9, 11, 8, tzinfo=UTC),
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """One Axle household."""
    return MockConfigEntry(
        domain="axle_energy",
        title="Axle Energy",
        entry_id="test-entry",
        data={CONF_API_KEY: "test-token"},
    )


@pytest.fixture(autouse=True)
def mock_client(mock_event: GridEvent) -> Iterator[AsyncMock]:
    """Mock the external dependency at the integration boundary."""
    with (
        patch(
            "homeassistant.components.axle_energy.AxleClient", autospec=True
        ) as client,
        patch(
            "homeassistant.components.axle_energy.config_flow.AxleClient", new=client
        ),
    ):
        client.return_value.get_event.return_value = mock_event
        yield client.return_value
