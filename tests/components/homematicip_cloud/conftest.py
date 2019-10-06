"""Initializer helpers for HomematicIP fake server."""
from unittest.mock import MagicMock, patch

from homematicip.aio.connection import AsyncConnection
import pytest

from homeassistant import config_entries
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    const as hmipc,
    hap as hmip_hap,
)
from homeassistant.core import HomeAssistant

from .helper import AUTH_TOKEN, HAPID, HomeTemplate

from tests.common import MockConfigEntry, mock_coro


@pytest.fixture(name="mock_connection")
def mock_connection_fixture():
    """Return a mockked connection."""
    connection = MagicMock(spec=AsyncConnection)

    def _rest_call_side_effect(path, body=None):
        return path, body

    connection._restCall.side_effect = _rest_call_side_effect  # pylint: disable=W0212
    connection.api_call.return_value = mock_coro(True)

    return connection


@pytest.fixture(name="default_mock_home")
def default_mock_home_fixture(mock_connection):
    """Create a fake homematic async home."""
    return HomeTemplate(connection=mock_connection).init_home().get_async_home_mock()


@pytest.fixture(name="hmip_config_entry")
def hmip_config_entry_fixture():
    """Create a fake config entriy for homematic ip cloud."""
    entry_data = {
        hmipc.HMIPC_HAPID: HAPID,
        hmipc.HMIPC_AUTHTOKEN: AUTH_TOKEN,
        hmipc.HMIPC_NAME: "",
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


@pytest.fixture(name="default_mock_hap")
async def default_mock_hap_fixture(
    hass: HomeAssistant, default_mock_home, hmip_config_entry
):
    """Create a fake homematic access point."""
    hass.config.components.add(HMIPC_DOMAIN)
    hap = hmip_hap.HomematicipHAP(hass, hmip_config_entry)
    with patch.object(hap, "get_hap", return_value=mock_coro(default_mock_home)):
        assert await hap.async_setup() is True

    hass.data[HMIPC_DOMAIN] = {HAPID: hap}

    await hass.async_block_till_done()

    return hap
