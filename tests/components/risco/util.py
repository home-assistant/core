"""Utilities for Risco tests."""
from unittest.mock import MagicMock, PropertyMock, patch

from pytest import fixture

from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "1234",
}
TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"


class MockRiscoCloud:
    """Mock for PyRisco cloud object."""

    def __init__(self, site_name="", site_uuid="", events=[], alarm=None):
        """Init mock object."""
        self._site_name = site_name
        self._site_uuid = site_uuid
        self._events = events
        self._alarm = alarm

    async def login(self, session=None):
        """Login to cloud."""
        return True

    async def close(self):
        """Close the connection."""
        return True

    async def get_state(self):
        """Get the alarm state."""
        return self._alarm

    async def get_events(self, newer_than, count):
        """Get the alarm event."""
        return self._events

    async def disarm(self, partition):
        """Disarm the alarm."""
        return self._alarm

    async def arm(self, partition):
        """Arm the alarm."""
        return self._alarm

    async def partial_arm(self, partition):
        """Partially-arm the alarm."""
        return self._alarm

    async def group_arm(self, partition, group):
        """Arm a specific group."""
        return self._alarm

    async def bypass_zone(self, zone, bypass):
        """Bypasses or unbypasses a zone."""
        return self._alarm

    @property
    def site_name(self):
        """Get the site name."""
        return self._site_name

    @property
    def site_uuid(self):
        """Get the site uuid."""
        return self._site_uuid


async def setup_risco(hass, events=[], alarm=None, options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, options=options)
    config_entry.add_to_hass(hass)

    mock = MockRiscoCloud(TEST_SITE_NAME, TEST_SITE_UUID, events, alarm)
    with patch(
        "homeassistant.components.risco.get_risco_cloud",
        return_value=mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return mock


def _zone_mock():
    return MagicMock(
        triggered=False,
        bypassed=False,
    )


@fixture
def two_zone_alarm():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: _zone_mock(), 1: _zone_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        alarm_mock,
        "zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ), patch.object(
        alarm_mock,
        "partitions",
        new_callable=PropertyMock(return_value=[]),
    ):
        yield alarm_mock
