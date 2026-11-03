"""Shared fixtures using the real Home Assistant test harness."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from xiaomi_weather import Location, parse_weather

from homeassistant.components.xiaomi_weather.const import DOMAIN


@pytest.fixture
def payload() -> dict[str, Any]:
    """Load a trimmed response captured from Xiaomi on 2026-09-08."""
    return load_json_object_fixture("weather.json", DOMAIN)


@pytest.fixture
def client(payload: dict[str, Any]) -> Generator[MagicMock]:
    """Mock the client where the integration imports it."""
    with (
        patch(
            "homeassistant.components.xiaomi_weather.coordinator.XiaomiWeatherClient",
            autospec=True,
        ) as mock,
        patch(
            "homeassistant.components.xiaomi_weather.config_flow.XiaomiWeatherClient",
            new=mock,
        ),
    ):
        client = mock.return_value
        client.get_weather.return_value = parse_weather(payload)
        client.locate.return_value = [
            Location("weathercn:101010100", "北京市", "中国", 39.9, 116.4, {})
        ]
        yield client


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
