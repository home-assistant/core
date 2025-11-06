"""Fixtures for Tado tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from mashumaro.codecs.orjson import ORJSONDecoder
import pytest
from tadoasync import Tado
from tadoasync.models import (
    Capabilities,
    Device,
    GetMe,
    HomeState,  # codespell:ignore homestate
    MobileDevice,
    TemperatureOffset,
    Weather,
    Zone,
    ZoneState,
    ZoneStates,
)

from homeassistant.components.tado import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_load_fixture,
    async_load_json_object_fixture,
)


@pytest.fixture
async def mock_tado_api(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Mock the Tado API."""
    with (
        patch("homeassistant.components.tado.Tado", autospec=True) as mock_tado,
        patch("homeassistant.components.tado.config_flow.Tado", new=mock_tado),
    ):
        client = mock_tado.return_value
        client.get_me.return_value = GetMe.from_dict(
            await async_load_json_object_fixture(hass, "me.json", DOMAIN)
        )
        client.get_zones.return_value = ORJSONDecoder(list[Zone]).decode(
            await async_load_fixture(hass, "zones.json", DOMAIN)
        )
        client.get_devices.return_value = ORJSONDecoder(list[Device]).decode(
            await async_load_fixture(hass, "devices.json", DOMAIN)
        )
        client.get_device_info.return_value = TemperatureOffset.from_dict(
            await async_load_json_object_fixture(
                hass, "device_temp_offset.json", DOMAIN
            )
        )
        zone_states = ZoneStates.from_dict(
            await async_load_json_object_fixture(hass, "zone_states.json", DOMAIN)
        )
        tado = Tado("", "")
        for zone in zone_states.zone_states.values():
            await tado.update_zone_data(zone)
        client.get_zone_states.return_value = dict(zone_states.zone_states.items())
        client.get_zone_state.return_value = ZoneState.from_dict(
            await async_load_json_object_fixture(hass, "zone_state.json", DOMAIN)
        )
        client.get_weather.return_value = Weather.from_dict(
            await async_load_json_object_fixture(hass, "weather.json", DOMAIN)
        )
        client.get_home_state.return_value = (
            HomeState.from_dict(  # codespell:ignore homestate
                await async_load_json_object_fixture(hass, "home_state.json", DOMAIN)
            )
        )
        client.get_capabilities.return_value = Capabilities.from_dict(
            await async_load_json_object_fixture(
                hass, "water_heater_zone_capabilities.json", DOMAIN
            )
        )
        client.get_mobile_devices.return_value = ORJSONDecoder(
            list[MobileDevice]
        ).decode(await async_load_fixture(hass, "mobile_devices.json", DOMAIN))
        client.device_verification_url = (
            "https://login.tado.com/oauth2/device?user_code=7BQ5ZQ"
        )
        client.refresh_token = "refresh"
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
