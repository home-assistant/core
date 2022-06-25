"""Fixtures for PVOutput integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pvo import Status, System
import pytest

from homeassistant.components.pvoutput.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_API_KEY: "tskey-MOCK", CONF_SYSTEM_ID: 12345},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.pvoutput.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_pvoutput_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked PVOutput client."""
    with patch(
        "homeassistant.components.pvoutput.config_flow.PVOutput", autospec=True
    ) as pvoutput_mock:
        yield pvoutput_mock.return_value


@pytest.fixture
def mock_pvoutput() -> Generator[None, MagicMock, None]:
    """Return a mocked PVOutput client."""
    status = Status(
        reported_date="20211229",
        reported_time="22:37",
        energy_consumption=1000,
        energy_generation=500,
        normalized_output=0.5,
        power_consumption=2500,
        power_generation=1500,
        temperature=20.2,
        voltage=220.5,
    )

    system = System(
        inverter_brand="Super Inverters Inc.",
        system_name="Frenck's Solar Farm",
    )

    with patch(
        "homeassistant.components.pvoutput.coordinator.PVOutput", autospec=True
    ) as pvoutput_mock:
        pvoutput = pvoutput_mock.return_value
        pvoutput.status.return_value = status
        pvoutput.system.return_value = system
        yield pvoutput


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pvoutput: MagicMock
) -> MockConfigEntry:
    """Set up the PVOutput integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
