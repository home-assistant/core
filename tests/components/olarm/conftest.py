"""Fixtures for the Olarm integration tests."""

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.olarm.const import (
    DOMAIN,
    OAUTH2_CLIENT_ID,
    OAUTH2_CLIENT_SECRET,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""
    # Load the `application_credentials` integration
    assert await async_setup_component(hass, "application_credentials", {})

    # Register the client credentials for Olarm OAuth
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Olarm"),
    )
