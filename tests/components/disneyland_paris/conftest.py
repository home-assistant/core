"""Common fixtures for the Disneyland Paris tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from dlpwait import Park, Parks
import pytest

from homeassistant.components.disneyland_paris.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.disneyland_paris.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
    )


@pytest.fixture(autouse=True)
def mock_disneyland_paris_client() -> Generator[AsyncMock]:
    """Mock a DLPWait client."""
    with (
        patch(
            "homeassistant.components.disneyland_paris.config_flow.DLPWaitAPI",
            autospec=True,
        ) as mock_cf_client,
        patch(
            "homeassistant.components.disneyland_paris.coordinator.DLPWaitAPI",
            autospec=True,
        ) as mock_coord_client,
    ):
        # Config flow client
        cf_client = mock_cf_client.return_value
        cf_client.update = AsyncMock(return_value=None)
        cf_client.parks = {
            Parks.DISNEYLAND: Park(
                slug=Parks.DISNEYLAND,
                opening_time=datetime(
                    2026, 3, 5, 9, 30, tzinfo=ZoneInfo(key="Europe/Paris")
                ),
                closing_time=datetime(
                    2026, 3, 5, 21, 0, tzinfo=ZoneInfo(key="Europe/Paris")
                ),
                attractions={},
                standby_wait_times={
                    "P1NA07": 10,
                    "P1AA00": 0,
                    "P1NA00": 5,
                    "P1DA03": 35,
                    "P1RA00": 45,
                    "P1NA01": None,
                    "P1DA04": 30,
                    "P1NA03": 45,
                    "P1DA10": None,
                    "P1NA16": None,
                    "P1RA10": 10,
                    "P1MA05": 0,
                    "P1NA05": 30,
                    "P1RA07": 0,
                    "P1AA02": 10,
                    "P1AA01": 5,
                    "P1NA06": 0,
                    "P1NA12": 0,
                    "P1NA02": 10,
                    "P1AA03": 0,
                    "P1NA09": 5,
                    "P1DA06": 5,
                    "P1NA13": 10,
                    "P1NA08": 5,
                    "P1MA04": None,
                    "P1DA07": 40,
                    "P1NA10": None,
                    "P1RA03": 15,
                    "P1AA08": None,
                    "P1AA04": 15,
                    "P1AA05": 0,
                    "P1RA05": 0,
                    "P1DA09": 20,
                    "P1DA08": 20,
                    "P1RA06": 20,
                },
            ),
            Parks.WALT_DISNEY_STUDIOS: Park(
                slug=Parks.WALT_DISNEY_STUDIOS,
                opening_time=datetime(
                    2026, 3, 5, 9, 30, tzinfo=ZoneInfo(key="Europe/Paris")
                ),
                closing_time=datetime(
                    2026, 3, 5, 21, 0, tzinfo=ZoneInfo(key="Europe/Paris")
                ),
                attractions={},
                standby_wait_times={
                    "P2AC01": 25,
                    "P2XA02": 25,
                    "P2XA00": 5,
                    "P2XA03": 60,
                    "P2EA00": 10,
                    "P2XA05": 20,
                    "P2XA06": 40,
                    "P2DA00": None,
                    "P2XA09": None,
                    "P2XA08": 15,
                    "P2AC02": 45,
                    "P2ZA02": 85,
                    "P2XA07": 50,
                },
            ),
        }

        # Coordinator client
        coord_client = mock_coord_client.return_value
        coord_client.update = cf_client.update
        coord_client.parks = cf_client.parks

        yield coord_client
