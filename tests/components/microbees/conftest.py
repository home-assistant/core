"""Conftest for microBees tests."""
from unittest.mock import AsyncMock, patch

from microBeesPy.microbees import Bee, MicroBees, Profile
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.microbees.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_json_array_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="microbees")
def mock_microbees():
    """Mock microbees."""

    devices_json = load_json_array_fixture("microbees/bees.json")
    devices = [Bee.from_dict(device) for device in devices_json]
    profile_json = load_json_array_fixture("microbees/profile.json")
    profile = Profile.from_dict(profile_json)

    mock = AsyncMock(spec=MicroBees)
    mock.getBees.return_value = devices
    mock.getMyProfile.return_value = profile

    with patch(
        "homeassistant.components.microbees.MicroBees",
        return_value=mock,
    ):
        yield mock
