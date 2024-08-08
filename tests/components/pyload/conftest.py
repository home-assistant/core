"""Fixtures for pyLoad integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyloadapi.types import LoginResponse, StatusServerResponse
import pytest

from homeassistant.components.pyload.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.typing import ConfigType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "pyload.local",
    CONF_PASSWORD: "test-password",
    CONF_PORT: 8000,
    CONF_SSL: True,
    CONF_USERNAME: "test-username",
    CONF_VERIFY_SSL: False,
}

YAML_INPUT = {
    CONF_HOST: "pyload.local",
    CONF_MONITORED_VARIABLES: ["speed"],
    CONF_NAME: "test-name",
    CONF_PASSWORD: "test-password",
    CONF_PLATFORM: "pyload",
    CONF_PORT: 8000,
    CONF_SSL: True,
    CONF_USERNAME: "test-username",
}
REAUTH_INPUT = {
    CONF_PASSWORD: "new-password",
    CONF_USERNAME: "new-username",
}

NEW_INPUT = {
    CONF_HOST: "pyload.local",
    CONF_PASSWORD: "new-password",
    CONF_PORT: 8000,
    CONF_SSL: True,
    CONF_USERNAME: "new-username",
    CONF_VERIFY_SSL: False,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pyload.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def pyload_config() -> ConfigType:
    """Mock pyload configuration entry."""
    return {"sensor": YAML_INPUT}


@pytest.fixture
def mock_pyloadapi() -> Generator[MagicMock]:
    """Mock PyLoadAPI."""
    with (
        patch(
            "homeassistant.components.pyload.PyLoadAPI", autospec=True
        ) as mock_client,
        patch("homeassistant.components.pyload.config_flow.PyLoadAPI", new=mock_client),
    ):
        client = mock_client.return_value
        client.username = "username"
        client.api_url = "https://pyload.local:8000/"
        client.login.return_value = LoginResponse(
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

        client.get_status.return_value = StatusServerResponse(
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
        client.version.return_value = "0.5.0"
        client.free_space.return_value = 99999999999
        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock pyLoad configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN, title=DEFAULT_NAME, data=USER_INPUT, entry_id="XXXXXXXXXXXXXX"
    )
