"""Shared fixtures for ZoneMinder integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from zoneminder.monitor import MonitorState, TimePeriod

from homeassistant.components.zoneminder.const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_HOST = "zm.example.com"
MOCK_HOST_2 = "zm2.example.com"
MOCK_ENTRY_ID = "01JZONEMINDER0000000000001"

MOCK_CONFIG_DATA: dict[str, Any] = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
    CONF_PATH: "/zm/",
    CONF_PATH_ZMS: "/zm/cgi-bin/nph-zms",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}

MOCK_OPTIONS: dict[str, Any] = {
    CONF_INCLUDE_ARCHIVED: False,
    CONF_COMMAND_ON: "modect",
    CONF_COMMAND_OFF: "monitor",
}


def create_mock_monitor(
    monitor_id: int = 1,
    name: str = "Front Door",
    function: MonitorState | None = MonitorState.MODECT,
    is_recording: bool = False,
    is_available: bool = True,
    events: dict[TimePeriod, int | None] | None = None,
) -> MagicMock:
    """Create a mock Monitor instance with configurable properties."""
    monitor = MagicMock()
    monitor.id = monitor_id
    monitor.name = name

    # function is both a property and a settable attribute in zm-py
    monitor.function = function

    monitor.is_recording = is_recording
    monitor.is_available = is_available
    monitor.mjpeg_image_url = f"http://{MOCK_HOST}/mjpeg/{monitor_id}"
    monitor.still_image_url = f"http://{MOCK_HOST}/still/{monitor_id}"

    if events is None:
        events = {
            TimePeriod.ALL: 100,
            TimePeriod.HOUR: 5,
            TimePeriod.DAY: 20,
            TimePeriod.WEEK: 50,
            TimePeriod.MONTH: 80,
        }

    def mock_get_events(
        time_period: TimePeriod, include_archived: bool = False
    ) -> int | None:
        return events.get(time_period, 0)

    monitor.get_events = MagicMock(side_effect=mock_get_events)

    return monitor


@pytest.fixture
def two_monitors() -> list[MagicMock]:
    """Pre-built list of 2 monitors."""
    return [
        create_mock_monitor(
            monitor_id=1,
            name="Front Door",
            function=MonitorState.MODECT,
            is_recording=True,
            is_available=True,
        ),
        create_mock_monitor(
            monitor_id=2,
            name="Back Yard",
            function=MonitorState.MONITOR,
            is_recording=False,
            is_available=True,
        ),
    ]


def create_mock_zm_client(monitors: list[MagicMock]) -> MagicMock:
    """Create a mock ZoneMinder client."""
    client = MagicMock()
    client.login.return_value = True
    client.get_monitors.return_value = monitors
    client.get_active_state.return_value = "Running"
    client.set_active_state.return_value = True

    # is_available and verify_ssl are properties in zm-py
    type(client).is_available = PropertyMock(return_value=True)
    type(client).verify_ssl = PropertyMock(return_value=True)

    return client


@pytest.fixture
def mock_zoneminder_client(two_monitors: list[MagicMock]) -> Generator[MagicMock]:
    """Mock the ZoneMinder client."""
    with patch(
        "homeassistant.components.zoneminder.ZoneMinder", autospec=True
    ) as mock_cls:
        client = create_mock_zm_client(two_monitors)
        mock_cls.return_value = client
        # Expose the class mock so tests can inspect constructor call_args
        client.mock_cls = mock_cls
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ZoneMinder config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST,
        data=MOCK_CONFIG_DATA,
        options=MOCK_OPTIONS,
        entry_id=MOCK_ENTRY_ID,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.zoneminder.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup
