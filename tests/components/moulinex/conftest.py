"""Fixtures for the Moulinex integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiomoulinex import (
    ApplianceShadow,
    ApplianceState,
    CookingStatus,
    Profile,
    Region,
    Tokens,
)
import jwt
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.moulinex.const import CONF_TOKENS, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_REGION

USER_ID = "005000000000001AAA"
EMAIL = "jane.doe@example.com"
COOKEO_ID = "11111111-2222-3333-4444-555555555555"
COMPANION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def build_tokens(user_id: str = USER_ID, refresh_token: str = "refresh-1") -> Tokens:
    """Build the tokens of an account, the id token carries the account id."""
    return Tokens(
        access_token="mock-access-token",
        id_token=jwt.encode(
            {"sub": f"https://login.example.com/id/00D000000000001/{user_id}"},
            "test-secret-long-enough-for-hmac-sha256",
        ),
        refresh_token=refresh_token,
    )


def load_status(name: str) -> CookingStatus:
    """Load a cooking status pushed by an appliance."""
    return CookingStatus.from_json(load_json_object_fixture(name, DOMAIN))


def load_shadow(name: str) -> ApplianceShadow:
    """Load a shadow pushed by the cloud."""
    return ApplianceShadow.from_json(load_json_object_fixture(name, DOMAIN))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Bypass the integration setup so the config flow can be tested in isolation."""
    with patch(
        "homeassistant.components.moulinex.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_profile() -> Profile:
    """Return the profile of an account with a Cookeo and a Companion."""
    return Profile.from_json(
        load_json_object_fixture("profile_two_appliances.json", DOMAIN)
    )


@pytest.fixture
def mock_login() -> Generator[AsyncMock]:
    """Patch the login used by the config flow."""
    with patch(
        "homeassistant.components.moulinex.config_flow.login",
        return_value=build_tokens(),
    ) as mock:
        yield mock


@pytest.fixture
def mock_fetch_profile(mock_profile: Profile) -> Generator[AsyncMock]:
    """Patch the profile request used by the config flow."""
    with patch(
        "homeassistant.components.moulinex.config_flow.fetch_profile",
        return_value=mock_profile,
    ) as mock:
        yield mock


@pytest.fixture
def mock_moulinex_client(mock_profile: Profile) -> Generator[MagicMock]:
    """Patch the client used by the coordinator, connected to both appliances."""
    with patch(
        "homeassistant.components.moulinex.coordinator.MoulinexClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.connected = True
        client.appliances = {
            appliance.thing_uuid: appliance for appliance in mock_profile.appliances
        }
        client.states = {
            COOKEO_ID: ApplianceState(
                status=load_status("status_warming.json"),
                shadow=load_shadow("shadow_get_accepted_online.json"),
            ),
            COMPANION_ID: ApplianceState(
                status=load_status("status_idle.json"),
                shadow=load_shadow("shadow_get_accepted_online.json"),
            ),
        }
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the config entry of a Moulinex account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=USER_ID,
        data={
            CONF_REGION: Region.MOULINEX_FR,
            CONF_EMAIL: EMAIL,
            CONF_TOKENS: build_tokens().to_dict(),
        },
        entry_id="01JMX5A0FF6G5V0QJX6HBC94T0",
    )
