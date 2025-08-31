"""August tests conftest."""

from unittest.mock import patch

import pytest
from yalexs.manager.ratelimit import _RateLimitChecker

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.august.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

USER_ID = "a76c25e5-49aa-4c14-cd0c-48a6931e2081"
CLIENT_ID = "1"


@pytest.fixture(name="mock_discovery", autouse=True)
def mock_discovery_fixture():
    """Mock discovery to avoid loading the whole bluetooth stack."""
    with patch(
        "homeassistant.components.august.data.discovery_flow.async_create_flow"
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
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "august",
            "token": {
                "access_token": jwt,
                "scope": "any",
                "expires_in": 86399,
                "refresh_token": "mock-refresh-token",
                "user_id": "mock-user-id",
                "expires_at": 1697753347,
            },
        },
        unique_id=USER_ID,
    )


@pytest.fixture(name="mock_legacy_config_entry")
def mock_legacy_config_entry_fixture() -> MockConfigEntry:
    """Return a legacy config entry without OAuth data."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "login_method": "email",
            "username": "my@email.tld",
            "password": "test-password",
            "install_id": None,
            "timeout": 10,
            "access_token_cache_file": ".my@email.tld.august.conf",
        },
        unique_id="my@email.tld",
    )


@pytest.fixture(name="jwt")
def load_jwt_fixture() -> str:
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN).strip("\n")


@pytest.fixture(name="legacy_jwt")
def load_legacy_jwt_fixture() -> str:
    """Load legacy JWT fixture data."""
    return load_fixture("legacy_jwt", DOMAIN).strip("\n")


@pytest.fixture(name="reauth_jwt")
def load_reauth_jwt_fixture() -> str:
    """Load reauth JWT fixture data."""
    return load_fixture("reauth_jwt", DOMAIN).strip("\n")


@pytest.fixture(name="migration_jwt")
def load_migration_jwt_fixture() -> str:
    """Load migration JWT fixture data (has email for legacy migration)."""
    return load_fixture("migration_jwt", DOMAIN).strip("\n")


@pytest.fixture(name="reauth_jwt_wrong_account")
def load_reauth_jwt_wrong_account_fixture() -> str:
    """Load JWT fixture data for wrong account during reauth."""
    # Different userId, no email match
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpbnN0YWxsSWQiOiIiLCJyZWdpb24iOiJpcmVsYW5kLXByb2QtYXdzIiwiYXBwbGljYXRpb25JZCI6IiIsInVzZXJJZCI6ImRpZmZlcmVudC11c2VyLWlkIiwidkluc3RhbGxJZCI6ZmFsc2UsInZQYXNzd29yZCI6dHJ1ZSwidkVtYWlsIjp0cnVlLCJ2UGhvbmUiOnRydWUsImhhc0luc3RhbGxJZCI6ZmFsc2UsImhhc1Bhc3N3b3JkIjpmYWxzZSwiaGFzRW1haWwiOmZhbHNlLCJoYXNQaG9uZSI6ZmFsc2UsImlzTG9ja2VkT3V0IjpmYWxzZSwiY2FwdGNoYSI6IiIsImVtYWlsIjpbImRpZmZlcmVudEBlbWFpbC50bGQiXSwicGhvbmUiOltdLCJleHBpcmVzQXQiOiIyMDI0LTEyLTE4VDEzOjU0OjA1LjEzNFoiLCJ0ZW1wb3JhcnlBY2NvdW50Q3JlYXRpb25QYXNzd29yZExpbmsiOiIiLCJpYXQiOjE3MjQxNjIwNDUsImV4cCI6MTczNDUzMDA0NSwib2F1dGgiOnsiYXBwX25hbWUiOiJIb21lIEFzc2lzdGFudCIsImNsaWVudF9pZCI6ImIzY2QzZjBiLWZiOTctNGQ2Yy1iZWU5LWFmN2FiMDQ3NThjNyIsInJlZGlyZWN0X3VyaSI6Imh0dHBzOi8vYWNjb3VudC1saW5rLm5hYnVjYXNhLmNvbS9hdXRob3JpemVfY2FsbGJhY2siLCJwYXJ0bmVyX2lkIjoiNjU3OTc0ODgxMDY2Y2E0OGM5OWMwODI2In19.mK9nTAv7glYgtpLIkVF_dsrjrkRKYemdKfKMkgnafCU"


@pytest.fixture(name="client_credentials", autouse=True)
async def mock_client_credentials_fixture(hass: HomeAssistant) -> None:
    """Mock client credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, "2"),
        DOMAIN,
    )


@pytest.fixture(name="skip_cloud", autouse=True)
def skip_cloud_fixture():
    """Skip setting up cloud.

    Cloud already has its own tests for account link.

    We do not need to test it here as we only need to test our
    usage of the oauth2 helpers.
    """
    with patch("homeassistant.components.cloud.async_setup", return_value=True):
        yield


@pytest.fixture
def mock_setup_entry():
    """Mock setup entry."""
    with patch(
        "homeassistant.components.august.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
