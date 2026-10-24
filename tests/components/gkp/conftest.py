"""Fixtures for the GKP integration tests."""

from collections.abc import Generator, Iterable
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from gkphomepython import Installation, Thermostat, ThermostatsResult
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.gkp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
TEST_USER_ID = "test-user-id"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_REFRESH_TOKEN = "test-refresh-token"
TEST_EXPIRES_AT = 9999999999

LIVING_ROOM_ID = "AABBCCDDEE01"
BEDROOM_ID = "AABBCCDDEE02"
LIVING_ROOM_ENTITY_ID = "climate.living_room"
BEDROOM_ENTITY_ID = "climate.bedroom"

# Shortly after the last report of the devices in the fixtures
NOW = "2026-09-30T12:06:00+00:00"


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time shortly after the devices last reported."""
    freezer.move_to(NOW)


@pytest.fixture(name="skip_cloud", autouse=True)
def skip_cloud_fixture():
    """Skip setting up cloud.

    Cloud already has its own tests for account link.

    We do not need to test it here as we only need to test our
    usage of the oauth2 helpers.
    """
    with patch("homeassistant.components.cloud.async_setup", return_value=True):
        yield


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="GKP"),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gkp.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def installations_data() -> list[dict[str, Any]]:
    """Return the raw installations of the user."""
    return load_json_array_fixture("installations.json", DOMAIN)


@pytest.fixture
def device_contents() -> dict[str, dict[str, Any]]:
    """Return the raw configuration content of each device."""
    return {
        LIVING_ROOM_ID: load_json_object_fixture("device_living_room.json", DOMAIN),
        BEDROOM_ID: load_json_object_fixture("device_bedroom.json", DOMAIN),
    }


@pytest.fixture
def mock_gkp_client(
    installations_data: list[dict[str, Any]],
    device_contents: dict[str, dict[str, Any]],
) -> Generator[AsyncMock]:
    """Mock a GKP client serving the fixtures, which tests may modify."""
    with patch(
        "homeassistant.components.gkp.GkpClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value

        async def get_installations() -> list[Installation]:
            return [Installation.from_dict(data) for data in installations_data]

        async def get_thermostat(
            device_id: str, installation: Installation
        ) -> Thermostat:
            return Thermostat.from_content(
                device_id, installation, device_contents[device_id]
            )

        async def get_thermostats(
            installations: Iterable[Installation],
        ) -> ThermostatsResult:
            return ThermostatsResult(
                thermostats={
                    device_id: Thermostat.from_content(
                        device_id, installation, device_contents[device_id]
                    )
                    for installation in installations
                    for device_id in installation.device_ids
                }
            )

        client.get_installations.side_effect = get_installations
        client.get_thermostat.side_effect = get_thermostat
        client.get_thermostats.side_effect = get_thermostats

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="GKP Home",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
        entry_id="01J0BC4QM2YBRP6H5G933CETI8",
        unique_id=TEST_USER_ID,
    )
