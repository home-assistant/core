"""Module for testing the KEM integration in Home Assistant."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kem.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture


@pytest.fixture(name="homes")
def kem_homes_fixture() -> list[dict[str, Any]]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("homes.json", DOMAIN)


@pytest.fixture(name="generator")
def kem_generator_fixture() -> dict[str, Any]:
    """Create sonos favorites fixture."""
    return load_json_value_fixture("generator.json", DOMAIN)


@pytest.fixture(name="kem_config_entry")
def kem_config_entry_fixture() -> MockConfigEntry:
    """Create a config entry fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "myemail@mail.com",
            CONF_PASSWORD: "password",
        },
        unique_id="myemail@mail.com",
    )


@pytest.fixture(name="kem_config_entry_with_refresh_token")
def kem_config_entry_with_refresh_token_fixture() -> MockConfigEntry:
    """Create a config entry fixture with refresh token."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "myemail@mail.com",
            CONF_PASSWORD: "password",
            CONF_REFRESH_TOKEN: "refresh_token",
        },
        unique_id="myemail@mail.com",
    )


@pytest.fixture(name="platform_sensor")
async def platform_sensor_fixture():
    """Patch KEM to only load Sensor platform."""
    with patch("homeassistant.components.kem.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.fixture
async def mock_kem(
    hass: HomeAssistant,
    homes: list[dict[str, Any]],
    generator: dict[str, Any],
    kem_config_entry: MockConfigEntry,
):
    """Mock KEM instance."""
    kem_config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.kem.data.AioKem.authenticate") as mock_auth,
        patch("homeassistant.components.kem.data.AioKem.get_homes") as mock_homes,
        patch(
            "homeassistant.components.kem.data.AioKem.get_generator_data"
        ) as mock_generator,
    ):
        mock_auth.return_value = None
        mock_homes.return_value = homes
        mock_generator.return_value = generator
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

        mocks = {
            "authenticate": mock_auth,
            "get_homes": mock_homes,
            "get_generator_data": mock_generator,
        }
        yield mocks


@pytest.fixture
async def mock_kem_authenticate(
    mock_kem: dict[str, AsyncMock],
):
    """Mock the authenticate method of the KEM instance."""
    return mock_kem["authenticate"]


@pytest.fixture
async def mock_kem_get_homes(
    mock_kem: dict[str, AsyncMock],
):
    """Mock the get_homes method of the KEM instance."""
    return mock_kem["get_homes"]


@pytest.fixture
async def mock_kem_get_generator_data(
    mock_kem: dict[str, AsyncMock],
):
    """Mock the get_generator_data method of the KEM instance."""
    return mock_kem["get_generator_data"]
