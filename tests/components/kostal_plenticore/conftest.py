"""Fixtures for Kostal Plenticore tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pykoplenti import MeData, VersionData
import pytest

from homeassistant.components.kostal_plenticore.helper import Plenticore
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked ConfigEntry for testing."""
    return MockConfigEntry(
        entry_id="2ab8dd92a62787ddfe213a67e09406bd",
        title="scb",
        domain="kostal_plenticore",
        data={"host": "192.168.1.2", "password": "SecretPassword"},
    )


@pytest.fixture
def mock_plenticore() -> Generator[Plenticore, None, None]:
    """Set up a Plenticore mock with some default values."""
    with patch(
        "homeassistant.components.kostal_plenticore.Plenticore", autospec=True
    ) as mock_api_class:
        # setup
        plenticore = mock_api_class.return_value
        plenticore.async_setup = AsyncMock()
        plenticore.async_setup.return_value = True

        plenticore.device_info = DeviceInfo(
            configuration_url="http://192.168.1.2",
            identifiers={("kostal_plenticore", "12345")},
            manufacturer="Kostal",
            model="PLENTICORE plus 10",
            name="scb",
            sw_version="IOC: 01.45 MC: 01.46",
        )

        plenticore.client = MagicMock()

        plenticore.client.get_version = AsyncMock()
        plenticore.client.get_version.return_value = VersionData(
            api_version="0.2.0",
            hostname="scb",
            name="PUCK RESTful API",
            sw_version="01.16.05025",
        )

        plenticore.client.get_me = AsyncMock()
        plenticore.client.get_me.return_value = MeData(
            locked=False,
            active=True,
            authenticated=True,
            permissions=[],
            anonymous=False,
            role="USER",
        )

        plenticore.client.get_process_data = AsyncMock()
        plenticore.client.get_settings = AsyncMock()

        yield plenticore


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up Kostal Plenticore integration for testing."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
