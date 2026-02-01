"""Fixtures for the Lyngdorf integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from lyngdorf.const import LyngdorfModel
import pytest

from homeassistant.components.lyngdorf.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Mock Lyngdorf",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_MODEL: "MP-60",
            "manufacturer": "Lyngdorf",
            "serial_number": "123456",
            "device_id": "aa:bb:cc:dd:ee:ff",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.lyngdorf.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_lyngdorf_model() -> LyngdorfModel:
    """Return a mocked Lyngdorf model."""
    return LyngdorfModel.MP_60


@pytest.fixture
def mock_receiver() -> Generator[MagicMock]:
    """Return a mocked Lyngdorf receiver."""
    with patch(
        "homeassistant.components.lyngdorf.async_create_receiver"
    ) as create_mock:
        receiver = MagicMock()
        receiver.async_connect = AsyncMock()
        receiver.async_disconnect = AsyncMock()
        receiver.name = "Mock Lyngdorf"
        create_mock.return_value = receiver
        yield receiver


@pytest.fixture
def mock_find_receiver_model() -> Generator[AsyncMock]:
    """Return a mocked async_find_receiver_model function."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model"
    ) as find_mock:
        find_mock.return_value = LyngdorfModel.MP_60
        yield find_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> MockConfigEntry:
    """Set up the Lyngdorf integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.lyngdorf.lookup_receiver_model") as lookup:
        lookup.return_value = LyngdorfModel.MP_60
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
