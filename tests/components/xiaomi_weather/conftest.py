"""Fixtures for the Xiaomi Weather client tests."""

from typing import Any

import pytest

from homeassistant.components.xiaomi_weather.const import DOMAIN

from tests.common import load_json_object_fixture


@pytest.fixture
def payload() -> dict[str, Any]:
    """Load a trimmed response captured from Xiaomi on 2026-09-08."""
    return load_json_object_fixture("weather.json", DOMAIN)
