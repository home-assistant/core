"""Test fixtures for bang_olufsen."""

from collections.abc import Generator
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
def mock_mozart_client() -> Generator[AsyncMock, None, None]:
    """Mock MozartClient."""

    with (
        patch(
            "homeassistant.components.bang_olufsen.MozartClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.bang_olufsen.config_flow.MozartClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_beolink_self = AsyncMock()
        client.get_beolink_self.return_value = BeolinkPeer(
            friendly_name=TEST_FRIENDLY_NAME, jid=TEST_JID_1
        )
        yield client


@pytest.fixture
def mock_setup_entry():
    """Mock successful setup entry."""
    with patch(
        "homeassistant.components.bang_olufsen.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
