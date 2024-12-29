"""Common fixtures for the SensorPush Cloud tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sensorpush_ha import SensorPushCloudApi, SensorPushCloudHelper

from homeassistant.components.sensorpush_cloud.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


def pytest_configure(config: pytest.Config) -> None:
    """Register markers for tests that use data."""
    config.addinivalue_line("markers", "data: mark test to run with specified data")


@pytest.fixture
def mock_api(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Override SensorPushCloudApi."""
    mock_api = AsyncMock(SensorPushCloudApi)
    with (
        patch(
            "homeassistant.components.sensorpush_cloud.config_flow.SensorPushCloudApi",
            return_value=mock_api,
        ),
    ):
        yield mock_api


@pytest.fixture
def mock_helper(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Override SensorPushCloudHelper."""
    mock_helper = AsyncMock(SensorPushCloudHelper)
    marker = request.node.get_closest_marker("data")
    if marker is not None:
        mock_helper.async_get_data.return_value = marker.args[0]
        mock_helper.async_get_device_ids.return_value = marker.args[0].keys()
    with (
        patch(
            "homeassistant.components.sensorpush_cloud.coordinator.SensorPushCloudHelper",
            return_value=mock_helper,
        ),
    ):
        yield mock_helper


@pytest.fixture
def make_config_entry(
    request: pytest.FixtureRequest,
) -> Callable[[dict[str, Any] | None], MockConfigEntry]:
    """ConfigEntry mock factory."""

    def _make_config_entry(data: dict[str, Any] | None = None):
        default_data = {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        }
        data = default_data if data is None else default_data | data
        return MockConfigEntry(domain=DOMAIN, data=data, entry_id=data[CONF_EMAIL])

    return _make_config_entry


@pytest.fixture
def mock_config_entry(
    make_config_entry: Callable[[dict[str, Any] | None], MockConfigEntry],
) -> MockConfigEntry:
    """ConfigEntry mock."""
    return make_config_entry()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sensorpush_cloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
