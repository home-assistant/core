"""Initializer helpers for HomematicIP fake server."""

from unittest.mock import AsyncMock, Mock, patch

from homematicip.async_home import AsyncHome
from homematicip.auth import Auth
from homematicip.base.enums import WeatherCondition, WeatherDayTime
from homematicip.connection.rest_connection import RestConnection
import pytest

from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    async_setup as hmip_async_setup,
)
from homeassistant.components.homematicip_cloud.const import (
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .helper import AUTH_TOKEN, HAPID, HAPPIN, HomeFactory

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(name="mock_connection")
def mock_connection_fixture() -> RestConnection:
    """Return a mocked connection."""
    connection = AsyncMock(spec=RestConnection)

    def _rest_call_side_effect(path, body=None, custom_header=None):
        return path, body

    connection.async_post.side_effect = _rest_call_side_effect

    return connection


@pytest.fixture(name="hmip_config_entry")
def hmip_config_entry_fixture() -> MockConfigEntry:
    """Create a mock config entry for homematic ip cloud."""
    entry_data = {
        HMIPC_HAPID: HAPID,
        HMIPC_AUTHTOKEN: AUTH_TOKEN,
        HMIPC_NAME: "",
        HMIPC_PIN: HAPPIN,
    }
    return MockConfigEntry(
        version=1,
        domain=HMIPC_DOMAIN,
        title="Home Test SN",
        unique_id=HAPID,
        data=entry_data,
        source=SOURCE_IMPORT,
    )


@pytest.fixture(name="default_mock_hap_factory")
async def default_mock_hap_factory_fixture(
    hass: HomeAssistant, mock_connection, hmip_config_entry: MockConfigEntry
) -> HomeFactory:
    """Create a mocked homematic access point."""
    return HomeFactory(hass, mock_connection, hmip_config_entry)


@pytest.fixture(name="hmip_config")
def hmip_config_fixture() -> ConfigType:
    """Create a config for homematic ip cloud."""

    entry_data = {
        HMIPC_HAPID: HAPID,
        HMIPC_AUTHTOKEN: AUTH_TOKEN,
        HMIPC_NAME: "",
        HMIPC_PIN: HAPPIN,
    }

    return {HMIPC_DOMAIN: [entry_data]}


@pytest.fixture(name="dummy_config")
def dummy_config_fixture() -> ConfigType:
    """Create a dummy config."""
    return {"blabla": None}


@pytest.fixture(name="mock_hap_with_service")
async def mock_hap_with_service_fixture(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory, dummy_config
) -> HomematicipHAP:
    """Create a fake homematic access point with hass services."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap()
    await hmip_async_setup(hass, dummy_config)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(HMIPC_DOMAIN)[0]
    entry.runtime_data = {HAPID: mock_hap}
    return mock_hap


@pytest.fixture(name="simple_mock_home")
def simple_mock_home_fixture():
    """Return a simple mocked connection."""

    mock_home = AsyncMock(
        spec=AsyncHome,
        name="Demo",
        devices=[],
        groups=[],
        location=Mock(),
        weather=Mock(
            temperature=0.0,
            weatherCondition=WeatherCondition.UNKNOWN,
            weatherDayTime=WeatherDayTime.DAY,
            minTemperature=0.0,
            maxTemperature=0.0,
            humidity=0,
            windSpeed=0.0,
            windDirection=0,
            vaporAmount=0.0,
        ),
        id=42,
        dutyCycle=88,
        connected=True,
        currentAPVersion="2.0.36",
        init_async=AsyncMock(),
        get_current_state_async=AsyncMock(),
    )

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome",
        autospec=True,
        return_value=mock_home,
    ):
        yield


@pytest.fixture(name="mock_connection_init")
def mock_connection_init_fixture():
    """Return a simple mocked connection."""

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.init_async",
            return_value=None,
            new_callable=AsyncMock,
        ),
    ):
        yield


@pytest.fixture(name="simple_mock_auth")
def simple_mock_auth_fixture() -> Auth:
    """Return a simple AsyncAuth Mock."""
    return AsyncMock(spec=Auth, pin=HAPPIN, create=True)
