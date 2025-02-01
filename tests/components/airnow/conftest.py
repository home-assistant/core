"""Define fixtures for AirNow tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.airnow.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from tests.common import MockConfigEntry, load_json_array_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any], options: dict[str, Any]
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
        unique_id=f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}",
        data=config,
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: "abc123",
        CONF_LATITUDE: 34.053718,
        CONF_LONGITUDE: -118.244842,
    }


@pytest.fixture(name="options")
def options_fixture() -> dict[str, Any]:
    """Define a config options data fixture."""
    return {
        CONF_RADIUS: 150,
    }


@pytest.fixture(name="data", scope="package")
def data_fixture() -> JsonArrayType:
    """Define a fixture for response data."""
    return load_json_array_fixture("response.json", "airnow")


@pytest.fixture(name="mock_api_get")
def mock_api_get_fixture(data: JsonArrayType) -> AsyncMock:
    """Define a fixture for a mock "get" coroutine function."""
    return AsyncMock(return_value=data)


@pytest.fixture(name="setup_airnow")
def setup_airnow_fixture(mock_api_get: AsyncMock) -> Generator[None]:
    """Define a fixture to set up AirNow."""
    with (
        patch("pyairnow.WebServiceAPI._get", mock_api_get),
        patch("homeassistant.components.airnow.PLATFORMS", []),
    ):
        yield
