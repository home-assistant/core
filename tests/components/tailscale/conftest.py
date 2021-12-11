"""Fixtures for Tailscale integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tailscale.models import Devices

from homeassistant.components.tailscale.const import CONF_TAILNET, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="homeassistant.github",
        domain=DOMAIN,
        data={CONF_TAILNET: "homeassistant.github", CONF_API_KEY: "tskey-MOCK"},
        unique_id="homeassistant.github",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tailscale.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_tailscale_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked Tailscale client."""
    with patch(
        "homeassistant.components.tailscale.config_flow.Tailscale", autospec=True
    ) as tailscale_mock:
        tailscale = tailscale_mock.return_value
        tailscale.devices.return_value = Devices.parse_raw(
            load_fixture("tailscale/devices.json")
        ).devices
        yield tailscale


@pytest.fixture
def mock_tailscale(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked Tailscale client."""
    fixture: str = "tailscale/devices.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    devices = Devices.parse_raw(load_fixture(fixture)).devices
    with patch(
        "homeassistant.components.tailscale.coordinator.Tailscale", autospec=True
    ) as tailscale_mock:
        tailscale = tailscale_mock.return_value
        tailscale.devices.return_value = devices
        yield tailscale


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tailscale: MagicMock
) -> MockConfigEntry:
    """Set up the Tailscale integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
