"""Define test fixtures for Ambient PWS."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.ambient_station.const import CONF_APP_KEY, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType, JsonObjectType

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture(name="api")
def api_fixture(data_devices: JsonArrayType) -> Mock:
    """Define a mock API object."""
    return Mock(get_devices=AsyncMock(return_value=data_devices))


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: "12345abcde12345abcde",
        CONF_APP_KEY: "67890fghij67890fghij",
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, Any]
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config,
        entry_id="382cf7643f016fd48b3fe52163fe8877",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="data_devices", scope="package")
def data_devices_fixture() -> JsonArrayType:
    """Define devices data."""
    return load_json_array_fixture("devices.json", "ambient_station")


@pytest.fixture(name="data_station", scope="package")
def data_station_fixture() -> JsonObjectType:
    """Define station data."""
    return load_json_object_fixture("station_data.json", "ambient_station")


@pytest.fixture(name="mock_aioambient")
def mock_aioambient_fixture(api: Mock) -> Generator[None]:
    """Define a fixture to patch aioambient."""
    with (
        patch(
            "homeassistant.components.ambient_station.config_flow.API",
            return_value=api,
        ),
        patch("aioambient.websocket.Websocket.connect"),
    ):
        yield


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_aioambient: None
) -> None:
    """Define a fixture to set up ambient_station."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
