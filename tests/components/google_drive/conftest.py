"""PyTest fixtures and test helpers."""

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_drive.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )
