"""Test Wallbox Init Component."""
import pytest
import requests_mock
from voluptuous.schema_builder import raises

from homeassistant.components import wallbox
from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

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


async def test_wallbox_setup_entry(hass: HomeAssistantType):
    """Test Wallbox Setup."""
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        assert await wallbox.async_setup_entry(hass, entry)

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":404}',
            status_code=404,
        )
        assert await wallbox.async_setup_entry(hass, entry) == False


async def test_wallbox_unload_entry(hass: HomeAssistantType):
    """Test Wallbox Unload."""
    hass.data[DOMAIN] = {"connections": {entry.entry_id: entry}}
    print(hass.data)

    assert await wallbox.async_unload_entry(hass, entry)

    hass.data[DOMAIN] = {"fail_entry": entry}

    with pytest.raises(KeyError):
        await wallbox.async_unload_entry(hass, entry)


async def test_wallbox_setup(hass: HomeAssistantType):
    """Test wallbox setup."""

    assert await wallbox.async_setup(hass, entry)


def test_hub_class():
    """Test hub class."""

    station = ("12345",)
    username = ("test-username",)
    password = "test-password"

    hub = wallbox.WallboxHub(station, username, password)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/('12345',)",
            text='{"Temperature": 100, "Location": "Toronto", "Datetime": "2020-07-23", "Units": "Celsius"}',
            status_code=200,
        )
        assert hub.authenticate()
        assert hub.get_data()

    with requests_mock.Mocker() as m, raises(wallbox.InvalidAuth):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=403)

        assert hub.authenticate()

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=404)

        assert hub.authenticate()

    with requests_mock.Mocker() as m, raises(wallbox.InvalidAuth):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=403)
        m.get(
            "https://api.wall-box.com/chargers/status/test",
            text="data",
            status_code=403,
        )
        assert hub.get_data()

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get("https://api.wall-box.com/auth/token/user", text="data", status_code=404)
        m.get(
            "https://api.wall-box.com/chargers/status/test",
            text="data",
            status_code=404,
        )
        assert hub.get_data()
