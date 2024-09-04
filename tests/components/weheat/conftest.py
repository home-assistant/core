"""Fixtures for Weheat tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.weheat.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_setup_entry():
    """Mock a successful setup."""
    with patch(
        "homeassistant.components.weheat.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
