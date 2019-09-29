"""Initializer helpers for HomematicIP fake server."""
from pathlib import Path
from unittest.mock import patch

import pytest

from homematicip.aio.home import AsyncHome

from homeassistant import config_entries
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    const as hmipc,
    hap as hmip_hap,
)
from .helper import AsyncConnectionLocal

from tests.common import mock_coro

HAPID = "3014F711A000000BAD0C0DED"
AUTH_TOKEN = "8A45BAA53BE37E3FCA58E9976EFA4C497DAFE55DB997DB9FD685236E5E63ED7DE"
HOME_JSON = "json_data/home.json"


@pytest.fixture
def fake_hmip_connection(request):
    """Create a fake homematic cloud connection."""
    home_path = Path(__file__).parent.joinpath(HOME_JSON)
    return AsyncConnectionLocal(home_path)


@pytest.fixture
async def fake_hmip_async_home(hass, fake_hmip_connection, loop):
    """Create a fake homematic async home."""
    home = AsyncHome(loop)
    home._connection = fake_hmip_connection
    home.name = ""
    home.label = "Access Point"
    home.modelType = "HmIP-HAP"
    home.set_auth_token(AUTH_TOKEN)
    await home.get_current_state()
    return home


@pytest.fixture
async def fake_hmip_config_entry():
    """Create a fake config entriy for homematic ip cloud."""
    entry_data = {
        hmipc.HMIPC_HAPID: HAPID,
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_NAME: "",
    }
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=HMIPC_DOMAIN,
        title=HAPID,
        data=entry_data,
        source="import",
        connection_class=config_entries.CONN_CLASS_CLOUD_PUSH,
        system_options={"disable_new_entities": False},
    )

    return config_entry


@pytest.fixture
async def fake_hmip_hap(hass, fake_hmip_async_home, fake_hmip_config_entry):
    """Create a fake homematic access point."""

    hass.config.components.add(HMIPC_DOMAIN)
    hap = hmip_hap.HomematicipHAP(hass, fake_hmip_config_entry)
    with patch.object(hap, "get_hap", return_value=mock_coro(fake_hmip_async_home)):
        assert await hap.async_setup() is True

    hass.data[HMIPC_DOMAIN] = {HAPID: hap}

    await hass.async_block_till_done()

    yield hap

    await hass.async_block_till_done()
