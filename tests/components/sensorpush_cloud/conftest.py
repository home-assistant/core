"""Common fixtures for the SensorPush Cloud tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sensorpush_cloud.api import SensorPushCloudApi
from homeassistant.components.sensorpush_cloud.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


def pytest_configure(config: pytest.Config) -> None:
    """Register markers for tests that use samples and sensors."""
    config.addinivalue_line(
        "markers", "samples: mark test to run with specified samples"
    )
    config.addinivalue_line(
        "markers", "sensors: mark test to run with specified sensors"
    )


@pytest.fixture
def mock_api(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Override SensorPushCloudApi."""
    mock_api = AsyncMock(SensorPushCloudApi)
    marker = request.node.get_closest_marker("sensors")
    if marker is not None:
        mock_api.async_sensors.return_value = marker.args[0]
    marker = request.node.get_closest_marker("samples")
    if marker is not None:
        mock_api.async_samples.return_value = marker.args[0]
    with (
        patch(
            "homeassistant.components.sensorpush_cloud.config_flow.SensorPushCloudApi",
            return_value=mock_api,
        ),
        patch(
            "homeassistant.components.sensorpush_cloud.coordinator.SensorPushCloudApi",
            return_value=mock_api,
        ),
    ):
        yield mock_api


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
