"""Shared fixtures using the real Home Assistant test harness."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xiaomi_weather.api import parse_weather
from homeassistant.components.xiaomi_weather.const import DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def payload() -> dict[str, Any]:
    """Load a trimmed response captured from Xiaomi on 2026-09-08."""
    return load_json_object_fixture("weather.json", DOMAIN)


@pytest.fixture
def client(payload: dict[str, Any]) -> Generator[AsyncMock]:
    """Mock only the external client boundary."""
    with patch(
        "homeassistant.components.xiaomi_weather.api.XiaomiWeatherClient.async_get_weather",
        return_value=parse_weather(payload),
    ) as mock:
        yield mock


@pytest.fixture
def entry() -> MockConfigEntry:
    """An entry for Beijing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Beijing",
        unique_id="101010100",
        data={
            "name": "Beijing",
            "city_id": "101010100",
            "latitude": 39.9042,
            "longitude": 116.4074,
        },
    )
