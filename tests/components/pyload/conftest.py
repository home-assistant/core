"""Fixtures for pyLoad integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyloadapi.types import LoginResponse, StatusServerResponse
import pytest

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import ConfigType


@pytest.fixture(name="pyload_config")
def mock_pyload_config_entry() -> ConfigType:
    """Mock pyload configuration entry."""
    return ConfigType(
        {
            "sensor": {
                CONF_PLATFORM: "pyload",
                CONF_HOST: "localhost",
                CONF_PORT: 8000,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_SSL: True,
                CONF_MONITORED_VARIABLES: ["speed"],
                CONF_NAME: "pyload",
            }
        }
    )


@pytest.fixture
def mock_pyloadapi() -> Generator[AsyncMock, None, None]:
    """Mock PyLoadAPI."""
    with (
        patch(
            "homeassistant.components.pyload.sensor.PyLoadAPI",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.username = "username"
        client.login.return_value = LoginResponse.from_dict(
            {
                "_permanent": True,
                "authenticated": True,
                "id": 2,
                "name": "username",
                "role": 0,
                "perms": 0,
                "template": "default",
                "_flashes": [["message", "Logged in successfully"]],
            }
        )
        client.get_status.return_value = StatusServerResponse.from_dict(
            {
                "pause": False,
                "active": 1,
                "queue": 6,
                "total": 37,
                "speed": 5405963.0,
                "download": True,
                "reconnect": False,
                "captcha": False,
            }
        )
        yield client
