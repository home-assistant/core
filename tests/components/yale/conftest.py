"""Yale tests conftest."""

from unittest.mock import patch

import pytest
from yalexs.manager.ratelimit import _RateLimitChecker

from homeassistant.components.yale.const import DOMAIN
from homeassistant.core import HomeAssistant

from .mocks import mock_client_credentials, mock_config_entry

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="mock_discovery", autouse=True)
def mock_discovery_fixture():
    """Mock discovery to avoid loading the whole bluetooth stack."""
    with patch(
        "homeassistant.components.yale.data.discovery_flow.async_create_flow"
    ) as mock_discovery:
        yield mock_discovery


@pytest.fixture(name="disable_ratelimit_checks", autouse=True)
def disable_ratelimit_checks_fixture():
    """Disable rate limit checks."""
    with patch.object(_RateLimitChecker, "register_wakeup"):
        yield


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture(jwt: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return mock_config_entry(jwt=jwt)


@pytest.fixture(name="jwt")
def load_jwt_fixture() -> str:
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN).strip("\n")


@pytest.fixture(name="reauth_jwt")
def load_reauth_jwt_fixture() -> str:
    """Load Fixture data."""
    return load_fixture("reauth_jwt", DOMAIN).strip("\n")


@pytest.fixture(name="reauth_jwt_wrong_account")
def load_reauth_jwt_wrong_account_fixture() -> str:
    """Load Fixture data."""
    return load_fixture("reauth_jwt_wrong_account", DOMAIN).strip("\n")


@pytest.fixture(name="client_credentials")
async def mock_client_credentials_fixture(hass: HomeAssistant) -> None:
    """Mock client credentials."""
    await mock_client_credentials(hass)
