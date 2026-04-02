"""Shared fixtures for ZoneMinder integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from zoneminder.monitor import MonitorState, TimePeriod

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

CONF_PATH_ZMS = "path_zms"

MOCK_HOST = "zm.example.com"
MOCK_HOST_2 = "zm2.example.com"


@pytest.fixture
def single_server_config() -> dict:
    """Return minimal single ZM server YAML config."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            }
        ]
    }


@pytest.fixture
def multi_server_config() -> dict:
    """Return two ZM servers with different settings."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            },
            {
                CONF_HOST: MOCK_HOST_2,
                CONF_USERNAME: "user2",
                CONF_PASSWORD: "pass2",
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_PATH: "/zoneminder/",
                CONF_PATH_ZMS: "/zoneminder/cgi-bin/nph-zms",
            },
        ]
    }


@pytest.fixture
def no_auth_config() -> dict:
    """Return server config without username/password."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
            }
        ]
    }


@pytest.fixture
def ssl_config() -> dict:
    """Return server config with SSL enabled, verify_ssl disabled."""
    return {
        DOMAIN: [
            {
                CONF_HOST: MOCK_HOST,
                CONF_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            }
        ]
    }


def create_mock_monitor(
    monitor_id: int = 1,
    name: str = "Front Door",
    function: MonitorState = MonitorState.MODECT,
    is_recording: bool = False,
    is_available: bool = True,
    mjpeg_image_url: str = "http://zm.example.com/mjpeg/1",
    still_image_url: str = "http://zm.example.com/still/1",
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
    monitor.mjpeg_image_url = mjpeg_image_url
    monitor.still_image_url = still_image_url

    if events is None:
        events = {
            TimePeriod.ALL: 100,
            TimePeriod.HOUR: 5,
            TimePeriod.DAY: 20,
            TimePeriod.WEEK: 50,
            TimePeriod.MONTH: 80,
        }

    def mock_get_events(time_period, include_archived=False):
        return events.get(time_period, 0)

    monitor.get_events = MagicMock(side_effect=mock_get_events)

    return monitor


@pytest.fixture
def mock_monitor():
    """Factory fixture returning a function to create mock Monitor instances."""
    return create_mock_monitor


@pytest.fixture
def two_monitors():
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


def create_mock_zm_client(
    is_available: bool = True,
    verify_ssl: bool = True,
    monitors: list | None = None,
    login_success: bool = True,
    active_state: str | None = "Running",
) -> MagicMock:
    """Create a mock ZoneMinder client."""
    client = MagicMock()
    client.login.return_value = login_success
    client.get_monitors.return_value = monitors or []

    # is_available and verify_ssl are properties in zm-py
    type(client).is_available = PropertyMock(return_value=is_available)
    type(client).verify_ssl = PropertyMock(return_value=verify_ssl)

    client.get_active_state.return_value = active_state
    client.set_active_state.return_value = True

    return client


@pytest.fixture
def mock_zoneminder_client(two_monitors: list[MagicMock]) -> Generator[MagicMock]:
    """Mock a ZoneMinder client."""
    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.login.return_value = True
        client.get_monitors.return_value = two_monitors
        client.get_active_state.return_value = "Running"
        client.set_active_state.return_value = True

        # is_available and verify_ssl are properties in zm-py
        type(client).is_available = PropertyMock(return_value=True)
        type(client).verify_ssl = PropertyMock(return_value=True)

        # Expose the class mock so tests can inspect constructor call_args
        # without needing their own inline patch block.
        client.mock_cls = mock_cls

        yield client


@pytest.fixture
def sensor_platform_config(single_server_config) -> dict:
    """Return sensor platform YAML with all monitored_conditions."""
    config = dict(single_server_config)
    config["sensor"] = [
        {
            "platform": DOMAIN,
            "include_archived": True,
            "monitored_conditions": ["all", "hour", "day", "week", "month"],
        }
    ]
    return config


@pytest.fixture
def switch_platform_config(single_server_config) -> dict:
    """Return switch platform YAML with command_on=Modect, command_off=Monitor."""
    config = dict(single_server_config)
    config["switch"] = [
        {
            "platform": DOMAIN,
            "command_on": "Modect",
            "command_off": "Monitor",
        }
    ]
    return config
