"""Fixtures for Weheat tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.weheat.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    MOCK_ACCESS_TOKEN,
    TEST_HP_UUID,
    TEST_MODEL,
    TEST_SN,
)


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


@pytest.fixture
def mock_heat_pump_info() -> HeatPumpDiscovery.HeatPumpInfo:
    """Create a HeatPumpInfo with default settings."""
    return HeatPumpDiscovery.HeatPumpInfo(
        TEST_HP_UUID, None, TEST_MODEL, TEST_SN, False
    )


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a session."""
    session = MagicMock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = {CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN}
    return session


@pytest.fixture
def mock_coordinator(mock_heat_pump_info: MagicMock) -> MagicMock:
    """Create a coordinator with heat_pump_info."""
    coordinator = MagicMock()
    coordinator.heat_pump_info = mock_heat_pump_info
    return coordinator
