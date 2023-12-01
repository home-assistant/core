"""Test fixtures for bangolufsen."""

from unittest.mock import AsyncMock, patch

from mozart_api.models import BeolinkPeer, VolumeLevel, VolumeSettings
import pytest

from homeassistant.components.bangolufsen.const import DOMAIN

from .const import (
    TEST_DATA_CONFIRM,
    TEST_DEFAULT_VOLUME,
    TEST_FRIENDLY_NAME,
    TEST_JID_1,
    TEST_MAX_VOLUME,
    TEST_NAME,
    TEST_SERIAL_NUMBER,
)

from tests.common import MockConfigEntry


class MockMozartClient:
    """Class for mocking MozartClient objects and methods."""

    # API call results
    get_beolink_self_result = BeolinkPeer(
        friendly_name=TEST_FRIENDLY_NAME, jid=TEST_JID_1
    )

    get_volume_settings_result = VolumeSettings(
        default=VolumeLevel(level=TEST_DEFAULT_VOLUME),
        maximum=VolumeLevel(level=TEST_MAX_VOLUME),
    )

    # API endpoints
    get_beolink_self = AsyncMock()
    get_beolink_self.return_value = get_beolink_self_result

    get_volume_settings = AsyncMock()
    get_volume_settings.return_value = get_volume_settings_result


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL_NUMBER,
        data=TEST_DATA_CONFIRM,
        title=TEST_NAME,
    )


@pytest.fixture
def mock_client():
    """Mock MozartClient."""

    client = MockMozartClient()

    with patch("mozart_api.mozart_client.MozartClient", return_value=client):
        yield client

    # Reset mocked API call counts and side effects
    client.get_volume_settings.reset_mock(side_effect=True)
    client.get_beolink_self.reset_mock(side_effect=True)


@pytest.fixture
def mock_setup_entry():
    """Mock successful setup entry."""
    with patch(
        "homeassistant.components.bangolufsen.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
