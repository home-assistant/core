"""Fixtures for the Tailwind integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from gotailwind import TailwindDeviceStatus
import pytest

from homeassistant.components.tailwind.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def device_fixture() -> str:
    """Return the device fixtures for a specific device."""
    return "iq3"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Tailwind iQ3",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.127",
            CONF_TOKEN: "123456",
        },
        unique_id="3c:e9:0e:6d:21:84",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tailwind.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_tailwind(device_fixture: str) -> Generator[MagicMock, None, None]:
    """Return a mocked Tailwind client."""
    with patch(
        "homeassistant.components.tailwind.coordinator.Tailwind", autospec=True
    ) as tailwind_mock, patch(
        "homeassistant.components.tailwind.config_flow.Tailwind",
        new=tailwind_mock,
    ):
        tailwind = tailwind_mock.return_value
        tailwind.status.return_value = TailwindDeviceStatus.from_json(
            load_fixture(f"{device_fixture}.json", DOMAIN)
        )
        yield tailwind


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailwind: MagicMock,
) -> MockConfigEntry:
    """Set up the Tailwind integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
