"""Fixtures for the Olarm integration tests."""

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.olarm.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Ensure the application credentials are registered for each test."""
    # Load the `application_credentials` integration so that the OAuth2 flow
    # can find the client id/secret we register below.
    assert await async_setup_component(hass, "application_credentials", {})

    # Register the client credentials used by the public Olarm OAuth client.
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )
