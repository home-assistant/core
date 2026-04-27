"""Common fixtures for the Notifications for Android TV / Fire TV tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.nfandroidtv.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import HOST, NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_notifications_android_tv() -> Generator[MagicMock]:
    """Mock notifications_android_tv."""

    with patch(
        "homeassistant.components.nfandroidtv.config_flow.Notifications", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.cls = mock_client

        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Notifications for Android TV / Fire TV configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST},
        entry_id="123456789",
    )
