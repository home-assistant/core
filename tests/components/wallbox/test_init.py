"""Test Wallbox Init Component."""
import json

import requests_mock
from voluptuous.schema_builder import raises

from homeassistant.components.wallbox.const import (
    CONF_CONNECTIONS,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry
from tests.components.wallbox import setup_integration

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


async def test_wallbox_unload_entry(hass: HomeAssistantType):
    """Test Wallbox Unload."""

    await setup_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_get_data(hass: HomeAssistantType):
    """Test hub class, get_data."""

    await setup_integration(hass)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response_rounding_error,
            status_code=200,
        )

        wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]
        assert await wallbox._async_update_data()


async def test_get_data_rounding_error(hass: HomeAssistantType):
    """Test hub class, get_data with rounding error."""

    await setup_integration(hass)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response_rounding_error,
            status_code=200,
        )

        wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]

        assert await wallbox._async_update_data()


async def test_authentication_exception(hass: HomeAssistantType):
    """Test hub class, authentication raises exception."""

    await setup_integration(hass)

    with requests_mock.Mocker() as m, raises(ConfigEntryAuthFailed):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":403}',
            status_code=403,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response_rounding_error,
            status_code=200,
        )

        wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]

        assert await wallbox._async_update_data()


async def test_connection_exception(hass: HomeAssistantType):
    """Test Connection Exception."""

    await setup_integration(hass)

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            json=test_response_rounding_error,
            status_code=200,
        )

        wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]

        assert await wallbox._async_update_data()


async def test_get_data_exception(hass: HomeAssistantType):
    """Test hub class, authentication raises exception."""

    await setup_integration(hass)

    with requests_mock.Mocker() as m, raises(ConnectionError):
        m.get(
            "https://api.wall-box.com/auth/token/user",
            text='{"jwt":"fakekeyhere","user_id":12345,"ttl":145656758,"error":false,"status":200}',
            status_code=200,
        )
        m.get(
            "https://api.wall-box.com/chargers/status/12345",
            text="data",
            status_code=404,
        )

        wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][entry.entry_id]

        assert await wallbox._async_update_data()
