"""Test fixtures for fitbit."""

from collections.abc import Awaitable, Callable, Generator
import datetime
from http import HTTPStatus
import time
from typing import Any
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.fitbit.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROFILE_USER_ID = "fitbit-api-user-id-1"
FAKE_TOKEN = "some-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"

PROFILE_API_URL = "https://api.fitbit.com/1/user/-/profile.json"
DEVICES_API_URL = "https://api.fitbit.com/1/user/-/devices.json"
TIMESERIES_API_URL_FORMAT = (
    "https://api.fitbit.com/1/user/-/{resource}/date/today/7d.json"
)


@pytest.fixture(name="token_expiration_time")
def mcok_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="fitbit_config_yaml")
def mock_fitbit_config_yaml(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for the yaml fitbit.conf file contents."""
    return {
        "access_token": FAKE_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "last_saved_at": token_expiration_time,
    }


@pytest.fixture(name="fitbit_config_setup", autouse=True)
def mock_fitbit_config_setup(
    fitbit_config_yaml: dict[str, Any],
) -> Generator[None, None, None]:
    """Fixture to mock out fitbit.conf file data loading and persistence."""

    with patch(
        "homeassistant.components.fitbit.sensor.os.path.isfile", return_value=True
    ), patch(
        "homeassistant.components.fitbit.sensor.load_json_object",
        return_value=fitbit_config_yaml,
    ), patch(
        "homeassistant.components.fitbit.sensor.save_json",
    ):
        yield


@pytest.fixture(name="monitored_resources")
def mock_monitored_resources() -> list[str] | None:
    """Fixture for the fitbit yaml config monitored_resources field."""
    return None


@pytest.fixture(name="configured_unit_system")
def mock_configured_unit_syststem() -> str | None:
    """Fixture for the fitbit yaml config monitored_resources field."""
    return None


@pytest.fixture(name="sensor_platform_config")
def mock_sensor_platform_config(
    monitored_resources: list[str] | None,
    configured_unit_system: str | None,
) -> dict[str, Any]:
    """Fixture for the fitbit sensor platform configuration data in configuration.yaml."""
    config = {}
    if monitored_resources is not None:
        config["monitored_resources"] = monitored_resources
    if configured_unit_system is not None:
        config["unit_system"] = configured_unit_system
    return config


@pytest.fixture(name="sensor_platform_setup")
async def mock_sensor_platform_setup(
    hass: HomeAssistant,
    sensor_platform_config: dict[str, Any],
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""

    async def run() -> bool:
        result = await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": DOMAIN,
                        **sensor_platform_config,
                    }
                ]
            },
        )
        await hass.async_block_till_done()
        return result

    return run


@pytest.fixture(name="profile_id")
def mock_profile_id() -> str:
    """Fixture for the profile id returned from the API response."""
    return PROFILE_USER_ID


@pytest.fixture(name="profile_locale")
def mock_profile_locale() -> str:
    """Fixture to set the API response for the user profile."""
    return "en_US"


@pytest.fixture(name="profile", autouse=True)
def mock_profile(requests_mock: Mocker, profile_id: str, profile_locale: str) -> None:
    """Fixture to setup fake requests made to Fitbit API during config flow."""
    requests_mock.register_uri(
        "GET",
        PROFILE_API_URL,
        status_code=HTTPStatus.OK,
        json={
            "user": {
                "encodedId": profile_id,
                "fullName": "My name",
                "locale": profile_locale,
            },
        },
    )


@pytest.fixture(name="devices_response")
def mock_device_response() -> list[dict[str, Any]]:
    """Return the list of devices."""
    return []


@pytest.fixture(autouse=True)
def mock_devices(requests_mock: Mocker, devices_response: dict[str, Any]) -> None:
    """Fixture to setup fake device responses."""
    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        status_code=HTTPStatus.OK,
        json=devices_response,
    )


def timeseries_response(resource: str, value: str) -> dict[str, Any]:
    """Create a timeseries response value."""
    return {
        resource: [{"dateTime": datetime.datetime.today().isoformat(), "value": value}]
    }


@pytest.fixture(name="register_timeseries")
def mock_register_timeseries(
    requests_mock: Mocker,
) -> Callable[[str, dict[str, Any]], None]:
    """Fixture to setup fake timeseries API responses."""

    def register(resource: str, response: dict[str, Any]) -> None:
        requests_mock.register_uri(
            "GET",
            TIMESERIES_API_URL_FORMAT.format(resource=resource),
            status_code=HTTPStatus.OK,
            json=response,
        )

    return register
