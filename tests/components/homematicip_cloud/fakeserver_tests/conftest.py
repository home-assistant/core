"""Initializer helpers for HomematicIP fake serverr."""
import asyncio
from functools import partial
from pathlib import Path
from unittest.mock import patch

from homematicip.aio.home import AsyncHome
from homematicip.home import Home
from homematicip_demo.fake_cloud_server import FakeCloudServer
from homematicip_demo.helper import no_ssl_verification
import pytest
from pytest_localserver.http import WSGIServer

from homeassistant import config_entries
from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    const as hmipc,
    hap as hmip_hap,
)

from tests.common import mock_coro

HAPID = "3014F711A000000BAD0C0DED"
AUTH_TOKEN = "8A45BAA53BE37E3FCA58E9976EFA4C497DAFE55DB997DB9FD685236E5E63ED7DE"
HOME_JSON = "json_data/home.json"


@pytest.fixture
def fake_hmip_cloud(request):
    """Create a fake homematic cloud. Defines the testserver funcarg."""

    home_path = Path(__file__).parent.joinpath(HOME_JSON)
    app = FakeCloudServer(home_path)
    server = WSGIServer(application=app)
    app.url = server.url
    server._server._timeout = 5  # added to allow timeouts in the fake server
    server.start()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture
def fake_hmip_home(fake_hmip_cloud):
    """Create a fake homematic sync home."""

    home = Home()
    with no_ssl_verification():
        lookup_url = "{}/getHost".format(fake_hmip_cloud.url)
        #    home.download_configuration = fake_home_download_configuration
        from homematicip.connection import Connection

        home._connection = Connection()
        home._fake_cloud = fake_hmip_cloud
        home.name = ""
        home.label = "Access Point"
        home.modelType = "HmIP-HAP"
        home.set_auth_token(AUTH_TOKEN)
        home._connection.init(accesspoint_id=HAPID, lookup_url=lookup_url)
        home.get_current_state()
    return home


@pytest.fixture
async def loop(event_loop):
    """Create an instance of the default event loop for each test case."""
    # event_loop from pytest_asyncio/plugin.py
    asyncio.set_event_loop(event_loop)
    return event_loop


@pytest.fixture
async def fake_hmip_async_home(hass, fake_hmip_cloud, loop):
    """Create a fake homematic async home."""

    home = AsyncHome(loop)
    home._connection._websession.post = partial(
        home._connection._websession.post, ssl=False
    )

    lookup_url = "{}/getHost".format(fake_hmip_cloud.url)
    home._fake_cloud = fake_hmip_cloud
    home.name = ""
    home.label = "Access Point"
    home.modelType = "HmIP-HAP"
    home.set_auth_token(AUTH_TOKEN)
    await home._connection.init(accesspoint_id=HAPID, lookup_url=lookup_url)
    await home.get_current_state()

    yield home

    await home._connection._websession.close()


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
