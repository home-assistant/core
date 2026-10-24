"""Fixtures for Hitron CODA tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hitron_coda.api import HitronCodaClient
from homeassistant.components.hitron_coda.const import DOMAIN

from .const import CONFIG, DEVICES


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the router's config entry."""
    return MockConfigEntry(domain=DOMAIN, title=CONFIG["host"], data=CONFIG)


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock HTTP calls from both the config flow and coordinator."""
    with (
        patch(
            "homeassistant.components.hitron_coda.config_flow.HitronCodaClient",
            autospec=HitronCodaClient,
        ) as mock,
        patch(
            "homeassistant.components.hitron_coda.coordinator.HitronCodaClient",
            new=mock,
        ),
        patch(
            "homeassistant.components.hitron_coda.device_tracker.HitronCodaClient",
            new=mock,
        ),
    ):
        client = mock.return_value
        client.get_devices.return_value = DEVICES.copy()
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-flow tests from setting up entities."""
    with patch(
        "homeassistant.components.hitron_coda.async_setup_entry", return_value=None
    ) as mock:
        yield mock
