"""Fixtures for the Cyclus NV integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from cyclus.const import WasteType
from cyclus.models import CalendarEvent
import pytest

from homeassistant.components.cyclus_nv.const import (
    CONF_BAG_ID,
    CONF_HOUSE_NUMBER,
    CONF_ZIPCODE,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={
            CONF_ZIPCODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
            CONF_BAG_ID: "0123456789abcdef",
        },
        unique_id="0123456789abcdef",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.cyclus_nv.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_cyclus_client() -> Generator[MagicMock]:
    """Return a mocked Cyclus NV client."""
    with (
        patch(
            "homeassistant.components.cyclus_nv.coordinator.CyclusClient",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.cyclus_nv.config_flow.CyclusClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.get_bag_id = AsyncMock(return_value="0123456789abcdef")
        client.get_calendar_events = AsyncMock(
            return_value=[
                CalendarEvent(
                    waste_type=WasteType.RESIDUAL_WASTE, pickup_date=date(2024, 1, 10)
                ),
                CalendarEvent(waste_type=WasteType.GFT, pickup_date=date(2024, 1, 17)),
                CalendarEvent(
                    waste_type=WasteType.PAPER, pickup_date=date(2024, 1, 24)
                ),
            ]
        )
        yield client
