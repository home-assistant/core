"""Fixtures for Tado tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from mashumaro.codecs.orjson import ORJSONDecoder
import pytest
from tadoasync.models import (
    Device,
    GetMe,
    HomeState,  # codespell:ignore homestate
    TemperatureOffset,
    Weather,
    Zone,
    ZoneStates,
)

from homeassistant.components.tado import CONF_REFRESH_TOKEN, DOMAIN

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture


@pytest.fixture
def mock_tado_api() -> Generator[MagicMock]:
    """Mock the Tado API."""
    with (
        patch("homeassistant.components.tado.Tado", autospec=True) as mock_tado,
        patch("homeassistant.components.tado.config_flow.Tado", new=mock_tado),
    ):
        client = mock_tado.return_value
        client.get_me.return_value = GetMe.from_dict(
            load_json_object_fixture("me.json", DOMAIN)
        )
        client.get_zones.return_value = ORJSONDecoder(list[Zone]).decode(
            load_fixture("zones.json", DOMAIN)
        )
        client.get_devices.return_value = ORJSONDecoder(list[Device]).decode(
            load_fixture("devices.json", DOMAIN)
        )
        client.get_device_info.return_value = TemperatureOffset.from_dict(
            load_json_object_fixture("device_temp_offset.json", DOMAIN)
        )
        client.get_zone_states.return_value = [
            ZoneStates.from_dict(load_json_object_fixture("zone_states.json", DOMAIN))
        ]
        client.get_weather.return_value = Weather.from_dict(
            load_json_object_fixture("weather.json", DOMAIN)
        )
        client.get_home_state.return_value = (
            HomeState.from_dict(  # codespell:ignore homestate
                load_json_object_fixture("home_state.json", DOMAIN)
            )
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.tado.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_REFRESH_TOKEN: "refresh",
        },
        unique_id="1",
        version=2,
    )
