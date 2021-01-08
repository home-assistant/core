"""Initializer helpers for HomematicIP fake server."""
from homematicip.aio.auth import AsyncAuth
from homematicip.aio.connection import AsyncConnection
from homematicip.aio.home import AsyncHome
from homematicip.base.enums import WeatherCondition, WeatherDayTime
import pytest

from homeassistant import config_entries
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
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .helper import AUTH_TOKEN, HAPID, HAPPIN, HomeFactory

from tests.async_mock import AsyncMock, MagicMock, Mock, patch
from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa


@pytest.fixture(name="mock_connection")
def mock_connection_fixture() -> AsyncConnection:
    """Return a mocked connection."""
    connection = MagicMock(spec=AsyncConnection)

    def _rest_call_side_effect(path, body=None):
        return path, body

    connection._restCall.side_effect = (  # pylint: disable=protected-access
        _rest_call_side_effect
    )
    connection.api_call = AsyncMock(return_value=True)
    connection.init = AsyncMock(side_effect=True)

    return connection


@pytest.fixture(name="hmip_config_entry")
def hmip_config_entry_fixture() -> config_entries.ConfigEntry:
    """Create a mock config entriy for homematic ip cloud."""
    entry_data = {
        HMIPC_HAPID: HAPID,
        HMIPC_AUTHTOKEN: AUTH_TOKEN,
        HMIPC_NAME: "",
        HMIPC_PIN: HAPPIN,
    }
    config_entry = MockConfigEntry(
        version=1,
        domain=HMIPC_DOMAIN,
        title="Home Test SN",
        unique_id=HAPID,
        data=entry_data,
        source=SOURCE_IMPORT,
        connection_class=config_entries.CONN_CLASS_CLOUD_PUSH,
        system_options={"disable_new_entities": False},
    )

    return config_entry


@pytest.fixture(name="default_mock_hap_factory")
async def default_mock_hap_factory_fixture(
    hass: HomeAssistantType, mock_connection, hmip_config_entry
) -> HomematicipHAP:
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
    hass: HomeAssistantType, default_mock_hap_factory, dummy_config
) -> HomematicipHAP:
    """Create a fake homematic access point with hass services."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap()
    await hmip_async_setup(hass, dummy_config)
    await hass.async_block_till_done()
    hass.data[HMIPC_DOMAIN] = {HAPID: mock_hap}
    return mock_hap


@pytest.fixture(name="simple_mock_home")
def simple_mock_home_fixture():
    """Return a simple mocked connection."""

    mock_home = Mock(
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

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome.init",
        return_value=None,
    ), patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncAuth.init",
        return_value=None,
    ):
        yield


@pytest.fixture(name="simple_mock_auth")
def simple_mock_auth_fixture() -> AsyncAuth:
    """Return a simple AsyncAuth Mock."""
    return Mock(spec=AsyncAuth, pin=HAPPIN, create=True)
