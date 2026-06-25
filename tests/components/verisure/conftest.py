"""Fixtures for Verisure integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.verisure.const import CONF_GIID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry

OVERVIEW = [
    {
        "data": {
            "installation": {
                "armState": {"status": "DISARMED", "statusType": "DISARMED"},
                "broadband": [{"status": "ONLINE"}],
                "cameras": [
                    {"device": {"deviceLabel": "cam-1"}, "status": "AVAILABLE"}
                ],
                "climates": [
                    {"device": {"deviceLabel": "climate-1"}, "temperature": 21}
                ],
                "doorWindows": [
                    {"device": {"deviceLabel": "door-1"}, "status": "CLOSED"}
                ],
                "smartLocks": [
                    {"device": {"deviceLabel": "lock-1"}, "status": "LOCKED"}
                ],
                "smartplugs": [{"device": {"deviceLabel": "plug-1"}, "status": "on"}],
            }
        }
    }
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_EMAIL: "verisure_my_pages@example.com",
            CONF_GIID: "12345",
            CONF_PASSWORD: "SuperS3cr3t!",
        },
        version=2,
    )


@pytest.fixture
def mock_verisure() -> Generator[MagicMock]:
    """Return a mocked Verisure session."""
    with patch(
        "homeassistant.components.verisure.coordinator.Verisure", autospec=True
    ) as mock_cls:
        session = mock_cls.return_value
        session.request.return_value = OVERVIEW
        yield session


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.verisure.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_verisure_config_flow() -> Generator[MagicMock]:
    """Return a mocked Tailscale client."""
    with patch(
        "homeassistant.components.verisure.config_flow.Verisure", autospec=True
    ) as verisure_mock:
        verisure = verisure_mock.return_value
        verisure.login.return_value = True
        verisure.get_installations.return_value = {
            "data": {
                "account": {
                    "installations": [
                        {
                            "giid": "12345",
                            "alias": "ascending",
                            "address": {"street": "12345th street"},
                        },
                        {
                            "giid": "54321",
                            "alias": "descending",
                            "address": {"street": "54321th street"},
                        },
                    ]
                }
            }
        }
        yield verisure
