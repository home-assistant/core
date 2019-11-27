"""Initializer helpers for HomematicIP fake server."""
from asynctest import MagicMock, Mock, patch
from homematicip.aio.auth import AsyncAuth
from homematicip.aio.connection import AsyncConnection
from homematicip.aio.home import AsyncHome
import pytest

from homeassistant import config_entries
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    async_setup as hmip_async_setup,
    const as hmipc,
    hap as hmip_hap,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .helper import AUTH_TOKEN, HAPID, HAPPIN, HomeTemplate

from tests.common import MockConfigEntry, mock_coro


@pytest.fixture(name="mock_connection")
def mock_connection_fixture() -> AsyncConnection:
    """Return a mocked connection."""
    connection = MagicMock(spec=AsyncConnection)

    def _rest_call_side_effect(path, body=None):
        return path, body

    connection._restCall.side_effect = (  # pylint: disable=protected-access
        _rest_call_side_effect
    )
    connection.api_call.return_value = mock_coro(True)
    connection.init.side_effect = mock_coro(True)

    return connection


@pytest.fixture(name="hmip_config_entry")
def hmip_config_entry_fixture() -> config_entries.ConfigEntry:
    """Create a mock config entriy for homematic ip cloud."""
    entry_data = {
        hmipc.HMIPC_HAPID: HAPID,
        hmipc.HMIPC_AUTHTOKEN: AUTH_TOKEN,
        hmipc.HMIPC_NAME: "",
        hmipc.HMIPC_PIN: HAPPIN,
    }
    config_entry = MockConfigEntry(
        version=1,
        domain=HMIPC_DOMAIN,
        title=HAPID,
        data=entry_data,
        source="import",
        connection_class=config_entries.CONN_CLASS_CLOUD_PUSH,
        system_options={"disable_new_entities": False},
    )

    return config_entry


@pytest.fixture(name="default_mock_home")
def default_mock_home_fixture(mock_connection) -> AsyncHome:
    """Create a fake homematic async home."""
    return HomeTemplate(connection=mock_connection).init_home().get_async_home_mock()


@pytest.fixture(name="default_mock_hap")
async def default_mock_hap_fixture(
    hass: HomeAssistantType, mock_connection, hmip_config_entry
) -> hmip_hap.HomematicipHAP:
    """Create a mocked homematic access point."""
    return await get_mock_hap(hass, mock_connection, hmip_config_entry)


async def get_mock_hap(
    hass: HomeAssistantType,
    mock_connection,
    hmip_config_entry: config_entries.ConfigEntry,
) -> hmip_hap.HomematicipHAP:
    """Create a mocked homematic access point."""
    hass.config.components.add(HMIPC_DOMAIN)
    hap = hmip_hap.HomematicipHAP(hass, hmip_config_entry)
    home_name = hmip_config_entry.data["name"]
    mock_home = (
        HomeTemplate(connection=mock_connection, home_name=home_name)
        .init_home()
        .get_async_home_mock()
    )
    with patch.object(hap, "get_hap", return_value=mock_coro(mock_home)):
        assert await hap.async_setup()
    mock_home.on_update(hap.async_update)
    mock_home.on_create(hap.async_create_entity)

    hass.data[HMIPC_DOMAIN] = {HAPID: hap}

    await hass.async_block_till_done()

    return hap


@pytest.fixture(name="hmip_config")
def hmip_config_fixture() -> ConfigType:
    """Create a config for homematic ip cloud."""

    entry_data = {
        hmipc.HMIPC_HAPID: HAPID,
        hmipc.HMIPC_AUTHTOKEN: AUTH_TOKEN,
        hmipc.HMIPC_NAME: "",
        hmipc.HMIPC_PIN: HAPPIN,
    }

    return {HMIPC_DOMAIN: [entry_data]}


@pytest.fixture(name="dummy_config")
def dummy_config_fixture() -> ConfigType:
    """Create a dummy config."""
    return {"blabla": None}


@pytest.fixture(name="mock_hap_with_service")
async def mock_hap_with_service_fixture(
    hass: HomeAssistantType, default_mock_hap, dummy_config
) -> hmip_hap.HomematicipHAP:
    """Create a fake homematic access point with hass services."""
    await hmip_async_setup(hass, dummy_config)
    await hass.async_block_till_done()
    hass.data[HMIPC_DOMAIN] = {HAPID: default_mock_hap}
    return default_mock_hap


@pytest.fixture(name="simple_mock_home")
def simple_mock_home_fixture() -> AsyncHome:
    """Return a simple AsyncHome Mock."""
    return Mock(
        spec=AsyncHome,
        devices=[],
        groups=[],
        location=Mock(),
        weather=Mock(create=True),
        id=42,
        dutyCycle=88,
        connected=True,
    )


@pytest.fixture(name="simple_mock_auth")
def simple_mock_auth_fixture() -> AsyncAuth:
    """Return a simple AsyncAuth Mock."""
    return Mock(spec=AsyncAuth, pin=HAPPIN, create=True)
