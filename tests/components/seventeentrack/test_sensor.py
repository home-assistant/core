"""Tests for the seventeentrack sensor."""
import datetime
from typing import Union
from unittest.mock import MagicMock, patch

from py17track.package import Package
import pytest

from homeassistant.components.seventeentrack.sensor import (
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed

VALID_CONFIG_MINIMAL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
    }
}

INVALID_CONFIG = {"sensor": {"platform": "seventeentrack", "boom": "test"}}

VALID_CONFIG_FULL = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: True,
        CONF_SHOW_DELIVERED: True,
    }
}

VALID_CONFIG_FULL_NO_DELIVERED = {
    "sensor": {
        "platform": "seventeentrack",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "test",
        CONF_SHOW_ARCHIVED: False,
        CONF_SHOW_DELIVERED: False,
    }
}

DEFAULT_SUMMARY = {
    "Not Found": 0,
    "In Transit": 0,
    "Expired": 0,
    "Ready to be Picked Up": 0,
    "Undelivered": 0,
    "Delivered": 0,
    "Returned": 0,
}

NEW_SUMMARY_DATA = {
    "Not Found": 1,
    "In Transit": 1,
    "Expired": 1,
    "Ready to be Picked Up": 1,
    "Undelivered": 1,
    "Delivered": 1,
    "Returned": 1,
}


class ClientMock:
    """Mock the py17track client to inject the ProfileMock."""

    def __init__(self, websession) -> None:
        """Mock the profile."""
        self.profile = ProfileMock()


class ProfileMock:
    """ProfileMock will mock data coming from 17track."""

    package_list = []
    login_result = True
    summary_data = DEFAULT_SUMMARY
    account_id = "123"

    @classmethod
    def reset(cls):
        """Reset data to defaults."""
        cls.package_list = []
        cls.login_result = True
        cls.summary_data = DEFAULT_SUMMARY
        cls.account_id = "123"

    def __init__(self) -> None:
        """Override Account id."""
        self.account_id = self.__class__.account_id

    async def login(self, email: str, password: str) -> bool:
        """Login mock."""
        return self.__class__.login_result

    async def packages(
        self, package_state: Union[int, str] = "", show_archived: bool = False
    ) -> list:
        """Packages mock."""
        return self.__class__.package_list[:]

    async def summary(self, show_archived: bool = False) -> dict:
        """Summary mock."""
        return self.__class__.summary_data


@pytest.fixture(autouse=True, name="mock_client")
def fixture_mock_client():
    """Mock py17track client."""
    with patch(
        "homeassistant.components.seventeentrack.sensor.SeventeenTrackClient",
        new=ClientMock,
    ):
        yield
    ProfileMock.reset()


async def _setup_seventeentrack(hass, config=None, summary_data=None):
    """Set up component using config."""
    if not config:
        config = VALID_CONFIG_MINIMAL
    if not summary_data:
        summary_data = {}

    ProfileMock.summary_data = summary_data
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()


async def _goto_future(hass, future=None):
    """Move to future."""
    if not future:
        future = utcnow() + datetime.timedelta(minutes=10)
    with patch("homeassistant.util.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()


async def test_full_valid_config(hass):
    """Ensure everything starts correctly."""
    assert await async_setup_component(hass, "sensor", VALID_CONFIG_FULL)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == len(ProfileMock.summary_data.keys())


async def test_valid_config(hass):
    """Ensure everything starts correctly."""
    assert await async_setup_component(hass, "sensor", VALID_CONFIG_MINIMAL)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == len(ProfileMock.summary_data.keys())


async def test_invalid_config(hass):
    """Ensure nothing is created when config is wrong."""
    assert await async_setup_component(hass, "sensor", INVALID_CONFIG)

    assert not hass.states.async_entity_ids()


async def test_add_package(hass):
    """Ensure package is added correctly when user add a new package."""
    package = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2
    )
    ProfileMock.package_list = [package]

    await _setup_seventeentrack(hass)
    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    assert len(hass.states.async_entity_ids()) == 1

    package2 = Package(
        "789", 206, "friendly name 2", "info text 2", "location 2", 206, 2
    )
    ProfileMock.package_list = [package, package2]

    await _goto_future(hass)

    assert hass.states.get("sensor.seventeentrack_package_789") is not None
    assert len(hass.states.async_entity_ids()) == 2


async def test_remove_package(hass):
    """Ensure entity is not there anymore if package is not there."""
    package1 = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2
    )
    package2 = Package(
        "789", 206, "friendly name 2", "info text 2", "location 2", 206, 2
    )

    ProfileMock.package_list = [package1, package2]

    await _setup_seventeentrack(hass)

    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    assert hass.states.get("sensor.seventeentrack_package_789") is not None
    assert len(hass.states.async_entity_ids()) == 2

    ProfileMock.package_list = [package2]

    await _goto_future(hass)

    assert hass.states.get("sensor.seventeentrack_package_456") is None
    assert hass.states.get("sensor.seventeentrack_package_789") is not None
    assert len(hass.states.async_entity_ids()) == 1


async def test_friendly_name_changed(hass):
    """Test friendly name change."""
    package = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2
    )
    ProfileMock.package_list = [package]

    await _setup_seventeentrack(hass)

    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    assert len(hass.states.async_entity_ids()) == 1

    package = Package(
        "456", 206, "friendly name 2", "info text 1", "location 1", 206, 2
    )
    ProfileMock.package_list = [package]

    await _goto_future(hass)

    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    entity = hass.data["entity_components"]["sensor"].get_entity(
        "sensor.seventeentrack_package_456"
    )
    assert entity.name == "Seventeentrack Package: friendly name 2"
    assert len(hass.states.async_entity_ids()) == 1


async def test_delivered_not_shown(hass):
    """Ensure delivered packages are not shown."""
    package = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2, 40
    )
    ProfileMock.package_list = [package]

    hass.components.persistent_notification = MagicMock()
    await _setup_seventeentrack(hass, VALID_CONFIG_FULL_NO_DELIVERED)
    await _goto_future(hass)

    assert not hass.states.async_entity_ids()
    hass.components.persistent_notification.create.assert_called()


async def test_delivered_shown(hass):
    """Ensure delivered packages are show when user choose to show them."""
    package = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2, 40
    )
    ProfileMock.package_list = [package]

    hass.components.persistent_notification = MagicMock()
    await _setup_seventeentrack(hass, VALID_CONFIG_FULL)

    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    assert len(hass.states.async_entity_ids()) == 1
    hass.components.persistent_notification.create.assert_not_called()


async def test_becomes_delivered_not_shown_notification(hass):
    """Ensure notification is triggered when package becomes delivered."""
    package = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2
    )
    ProfileMock.package_list = [package]

    await _setup_seventeentrack(hass, VALID_CONFIG_FULL_NO_DELIVERED)

    assert hass.states.get("sensor.seventeentrack_package_456") is not None
    assert len(hass.states.async_entity_ids()) == 1

    package_delivered = Package(
        "456", 206, "friendly name 1", "info text 1", "location 1", 206, 2, 40
    )
    ProfileMock.package_list = [package_delivered]

    hass.components.persistent_notification = MagicMock()
    await _goto_future(hass)

    hass.components.persistent_notification.create.assert_called()
    assert not hass.states.async_entity_ids()


async def test_summary_correctly_updated(hass):
    """Ensure summary entities are not duplicated."""
    await _setup_seventeentrack(hass, summary_data=DEFAULT_SUMMARY)

    assert len(hass.states.async_entity_ids()) == 7
    for state in hass.states.async_all():
        assert state.state == "0"

    ProfileMock.summary_data = NEW_SUMMARY_DATA

    await _goto_future(hass)

    assert len(hass.states.async_entity_ids()) == 7
    for state in hass.states.async_all():
        assert state.state == "1"
