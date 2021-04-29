"""Test the Whirlpool Sixth Sense init."""
from unittest import mock
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import aiohttp
import pytest

from homeassistant.components.whirlpool import async_setup_entry, async_unload_entry
from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def init_integration(hass, entry_id):
    """Do integration initialization."""
    config_entry_mock = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "user@mail.com",
            "password": "pass",
        },
        entry_id=entry_id,
    )
    return await async_setup_entry(hass, config_entry_mock)


@pytest.fixture(name="auth_api")
def auth_api_fixture():
    """Set up auth API fixture."""
    with mock.patch("homeassistant.components.whirlpool.Auth") as mock_auth_api:
        yield mock_auth_api


async def test_setup_entry(hass, auth_api):
    """Test setup entry."""
    auth_api.return_value.do_auth = AsyncMock()
    auth_api.return_value.is_access_token_valid.return_value = True

    entry_id = str(uuid4())
    assert await init_integration(hass, entry_id)
    auth_api.return_value.do_auth.assert_called_once_with(store=False)
    assert hass.data[DOMAIN][entry_id]["auth"] is not None


async def test_setup_entry_http_exception(hass, auth_api):
    """Test setup entry."""
    auth_api.return_value.do_auth = AsyncMock(side_effect=aiohttp.ClientConnectionError)

    entry_id = str(uuid4())
    with pytest.raises(ConfigEntryNotReady):
        await init_integration(hass, entry_id)
    assert entry_id not in hass.data[DOMAIN]


async def test_setup_entry_auth_failed(hass, auth_api):
    """Test setup entry."""
    auth_api.return_value.do_auth = AsyncMock()
    auth_api.return_value.is_access_token_valid.return_value = False

    entry_id = str(uuid4())
    with pytest.raises(ConfigEntryNotReady):
        await init_integration(hass, entry_id)
    assert entry_id not in hass.data[DOMAIN]


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry_id = str(uuid4())
    config_entry_mock = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "user@mail.com",
            "password": "pass",
        },
        entry_id=entry_id,
    )
    # Put random content at the location where the client should have been placed by setup
    hass.data.setdefault(DOMAIN, {})[entry_id] = {"auth": Mock}

    await async_unload_entry(hass, config_entry_mock)
    assert entry_id not in hass.data[DOMAIN]
