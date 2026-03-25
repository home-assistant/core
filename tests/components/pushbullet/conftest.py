"""Conftest for pushbullet integration."""

from pushbullet import PushBullet
import pytest
from requests_mock import Mocker

from tests.common import load_fixture


@pytest.fixture(autouse=True)
def requests_mock_fixture(requests_mock: Mocker) -> None:
    """Fixture to provide a aioclient mocker."""
    requests_mock.get(
        PushBullet.DEVICES_URL,
        text=load_fixture("devices.json", "pushbullet"),
    )
    requests_mock.get(
        PushBullet.ME_URL,
        text=load_fixture("user_info.json", "pushbullet"),
    )
    requests_mock.get(
        PushBullet.CHATS_URL,
        text=load_fixture("chats.json", "pushbullet"),
    )
    requests_mock.get(
        PushBullet.CHANNELS_URL,
        text=load_fixture("channels.json", "pushbullet"),
    )
