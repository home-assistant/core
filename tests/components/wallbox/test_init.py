"""Test Wallbox Init Component."""
import json

import pytest
import requests_mock
from voluptuous.schema_builder import raises

from homeassistant.components import wallbox
from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

entry = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_STATION: "12345",
    },
    entry_id="testEntry",
)

test_response = json.loads(
    '{"charging_power": 0,"max_available_power": 25,"charging_speed": 0,"added_range": 372,"added_energy": 44.697}'
)

test_response_rounding_error = json.loads(
    '{"charging_power": "XX","max_available_power": "xx","charging_speed": 0,"added_range": "xx","added_energy": "XX"}'
)


async def test_wallbox_setup_entry(hass: HomeAssistant):
    """Test Wallbox Setup."""
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            text='{"Temperature": 100, "Location": "Toronto", "Datetime": "2020-07-23", "Units": "Celsius"}',
            status_code=200,
        )
        assert await wallbox.async_setup_entry(hass, entry)

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":404}',
            status_code=404,
        )
        assert await wallbox.async_setup_entry(hass, entry) is False


async def test_wallbox_unload_entry(hass: HomeAssistant):
    """Test Wallbox Unload."""
    hass.data[DOMAIN] = {"connections": {entry.entry_id: entry}}

    assert await wallbox.async_unload_entry(hass, entry)

    hass.data[DOMAIN] = {"fail_entry": entry}

    with pytest.raises(KeyError):
        await wallbox.async_unload_entry(hass, entry)


async def test_get_data(hass: HomeAssistant):
    """Test hub class, get_data."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = wallbox.WallboxHub(station, username, password, hass)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/('12345',)",
            json=test_response,
            status_code=200,
        )
        assert await hub.async_get_data()


async def test_get_data_rounding_error(hass: HomeAssistant):
    """Test hub class, get_data with rounding error."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = wallbox.WallboxHub(station, username, password, hass)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/('12345',)",
            json=test_response_rounding_error,
            status_code=200,
        )
        assert await hub.async_get_data()


async def test_authentication_exception(hass: HomeAssistant):
    """Test hub class, authentication raises exception."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = wallbox.WallboxHub(station, username, password, hass)

    with requests_mock.Mocker() as m, raises(wallbox.InvalidAuth):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=403)

        assert await hub.async_authenticate()

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=404)

        assert await hub.async_authenticate()

    with requests_mock.Mocker() as m, raises(wallbox.InvalidAuth):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=403)
        m.get(
            "https://api.wall-box.com/chargers/status/test",
            json=test_response,
            status_code=403,
        )
        assert await hub.async_get_data()


async def test_get_data_exception(hass: HomeAssistant):
    """Test hub class, authentication raises exception."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = wallbox.WallboxHub(station, username, password, hass)

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/('12345',)",
            text="data",
            status_code=404,
        )
        assert await hub.async_get_data()
