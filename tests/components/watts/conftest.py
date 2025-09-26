"""Fixtures for the Watts integration tests."""

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.watts.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""

    assert await async_setup_component(hass, "application_credentials", {})

    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Watts"),
    )
