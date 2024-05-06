"""Test fixtures for bang_olufsen."""

from unittest.mock import AsyncMock, patch

from mozart_api.models import BeolinkPeer
import pytest

from homeassistant.components.bang_olufsen.const import DOMAIN

from .const import (
    TEST_DATA_CREATE_ENTRY,
    TEST_FRIENDLY_NAME,
    TEST_JID_1,
    TEST_NAME,
    TEST_SERIAL_NUMBER,
)

from tests.common import MockConfigEntry


class MockMozartClient:
    """Class for mocking MozartClient objects and methods."""

    async def __aenter__(self):
        """Mock async context entry."""

    async def __aexit__(self, exc_type, exc, tb):
        """Mock async context exit."""

    # API call results
    get_beolink_self_result = BeolinkPeer(
        friendly_name=TEST_FRIENDLY_NAME, jid=TEST_JID_1
    )

    # API endpoints
    get_beolink_self = AsyncMock()
    get_beolink_self.return_value = get_beolink_self_result


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL_NUMBER,
        data=TEST_DATA_CREATE_ENTRY,
        title=TEST_NAME,
    )


@pytest.fixture
def mock_client():
    """Mock MozartClient."""

    client = MockMozartClient()

    with patch("mozart_api.mozart_client.MozartClient", return_value=client):
        yield client

    # Reset mocked API call counts and side effects
    client.get_beolink_self.reset_mock(side_effect=True)


@pytest.fixture
def mock_setup_entry():
    """Mock successful setup entry."""
    with patch(
        "homeassistant.components.bang_olufsen.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
