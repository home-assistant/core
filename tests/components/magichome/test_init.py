"""The tests for the MagicHome component."""
import json
import os

import pytest

from unittest.mock import patch
from magichome import MagicHomeApi
from homeassistant.components import magichome
from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed, mock_coro


@pytest.fixture(autouse=True)
def mock_history(hass):
    """Mock history component loaded."""
    hass.config.components.add("history")


@pytest.fixture(autouse=True)
def magichome_cleanup(hass):
    """Clean up device tracker magichome file."""
    yield
    try:
        os.remove(hass.config.path(YAML_DEVICES))
    except FileNotFoundError:
        pass


async def test_setting_up_magichome(hass):
    """Test if we can set up the magichome and dump it to JSON."""
    assert await async_setup_component(
        hass,
        magichome.DOMAIN,
        {
            "magichome": {
                "username": "test@user.com",
                "password": "123456",
                "company": "ZG001",
                "platform": "ZG001",
            }
        },
    )
    await hass.async_start()

    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:
        pytest.fail(
            "Unable to convert all magichome entities to JSON. "
            "Wrong data in state machine!"
        )


async def test_magichome_api(hass):
    magichome = MagicHomeApi()
    assert magichome.init("test@user.com", "123456", "ZG001", "ZG001")
    devices = magichome.discover_devices()
    assert devices != []


async def mock_magichome_api_fail(hass):
    mock_of_magic_home_api = MagicHomeApi()
    assert mock_of_magic_home_api.init("test@user.com", "password", "ZG001", "ZG001")
