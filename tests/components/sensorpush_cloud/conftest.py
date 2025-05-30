"""Common fixtures for the SensorPush Cloud tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from sensorpush_ha import SensorPushCloudApi

from homeassistant.components.sensorpush_cloud.const import DOMAIN
from homeassistant.const import CONF_EMAIL

from .const import CONF_DATA, MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
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
def mock_helper() -> Generator[AsyncMock]:
    """Override SensorPushCloudHelper."""
    with (
        patch(
            "homeassistant.components.sensorpush_cloud.coordinator.SensorPushCloudHelper",
            autospec=True,
        ) as mock_helper,
    ):
        helper = mock_helper.return_value
        helper.async_get_data.return_value = MOCK_DATA
        yield helper


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """ConfigEntry mock."""
    return MockConfigEntry(
        domain=DOMAIN, data=CONF_DATA, unique_id=CONF_DATA[CONF_EMAIL]
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sensorpush_cloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
