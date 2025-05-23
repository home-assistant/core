"""Provide common smhi fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pysmhi.smhi_forecast import SMHIForecast, SMHIPointForecast
import pytest

from homeassistant.components.smhi import PLATFORMS
from homeassistant.components.smhi.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant

from . import TEST_CONFIG

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smhi.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="load_platforms")
async def patch_platform_constant() -> list[Platform]:
    """Return list of platforms to load."""
    return PLATFORMS


@pytest.fixture
async def load_int(
    hass: HomeAssistant,
    mock_client: SMHIPointForecast,
    load_platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the SMHI integration."""
    hass.config.latitude = "59.32624"
    hass.config.longitude = "17.84197"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        entry_id="01JMZDH8N5PFHGJNYKKYCSCWER",
        unique_id="59.32624-17.84197",
        version=3,
        title="Test",
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.smhi.PLATFORMS", load_platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="mock_client")
async def get_client(
    hass: HomeAssistant,
    get_data: tuple[list[SMHIForecast], list[SMHIForecast], list[SMHIForecast]],
) -> AsyncGenerator[MagicMock]:
    """Mock SMHIPointForecast client."""

    with (
        patch(
            "homeassistant.components.smhi.coordinator.SMHIPointForecast",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.smhi.config_flow.SMHIPointForecast",
            return_value=mock_client.return_value,
        ),
    ):
        client = mock_client.return_value
        client.async_get_daily_forecast.return_value = get_data[0]
        client.async_get_twice_daily_forecast.return_value = get_data[1]
        client.async_get_hourly_forecast.return_value = get_data[2]
        yield client


@pytest.fixture(name="get_data")
async def get_data_from_library(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    load_json: dict[str, Any],
) -> AsyncGenerator[tuple[list[SMHIForecast], list[SMHIForecast], list[SMHIForecast]]]:
    """Get data from api."""
    client = SMHIPointForecast(
        TEST_CONFIG[CONF_LOCATION][CONF_LONGITUDE],
        TEST_CONFIG[CONF_LOCATION][CONF_LATITUDE],
        aioclient_mock.create_session(hass.loop),
    )
    with patch.object(
        client._api,
        "async_get_data",
        return_value=load_json,
    ):
        data_daily = await client.async_get_daily_forecast()
        data_twice_daily = await client.async_get_twice_daily_forecast()
        data_hourly = await client.async_get_hourly_forecast()

    yield (data_daily, data_twice_daily, data_hourly)
    await client._api._session.close()


@pytest.fixture(name="load_json")
def load_json_from_fixture(
    load_data: tuple[str, str, str],
    to_load: int,
) -> dict[str, Any]:
    """Load fixture with json data and return."""
    return json.loads(load_data[to_load])


@pytest.fixture(name="load_data", scope="package")
def load_data_from_fixture() -> tuple[str, str, str]:
    """Load fixture with fixture data and return."""
    return (
        load_fixture("smhi.json", "smhi"),
        load_fixture("smhi_night.json", "smhi"),
        load_fixture("smhi_short.json", "smhi"),
    )


@pytest.fixture
def to_load() -> int:
    """Fixture to load."""
    return 0
