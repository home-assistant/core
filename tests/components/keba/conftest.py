"""Fixtures for KEBA integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.keba.const import (
    CONF_FS,
    CONF_FS_FALLBACK,
    CONF_FS_PERSIST,
    CONF_FS_TIMEOUT,
    CONF_RFID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_RFID: "",
    CONF_FS: False,
    CONF_FS_TIMEOUT: 30,
    CONF_FS_FALLBACK: 6,
    CONF_FS_PERSIST: 0,
}

_KEBA_DATA: dict[str, Any] = {
    "Serial": "12345678",
    "Product": "KC-P30",
    "Enable user": 1,
    "Authreq": 1,
    "Online": True,
    "Plug_plugged": True,
    "Plug_wallbox": True,
    "Plug_locked": False,
    "Plug_EV": True,
    "State_on": True,
    "State_details": "charging",
    "Max curr": 16,
    "FS_on": False,
    "Tmo FS": 30,
    "Curr FS": 6,
    "P": 2.5,
    "PF": 0.98,
    "U1": 230,
    "U2": 230,
    "U3": 230,
    "I1": 3.6,
    "I2": 3.6,
    "I3": 3.6,
    "Curr user": 16,
    "Curr HW": 32,
    "Setenergy": 10.0,
    "E pres": 5.2,  # codespell:ignore pres
    "E total": 100.5,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        unique_id="12345678",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.keba.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_keba() -> Generator[MagicMock]:
    """Return a mocked KebaHandler."""
    handler = MagicMock()
    handler.setup = AsyncMock(return_value=True)
    handler.set_failsafe = AsyncMock()
    handler.request_data = AsyncMock()
    handler.set_text = AsyncMock()
    handler.enable = AsyncMock()
    handler.start = AsyncMock()
    handler.stop = AsyncMock()
    handler.set_energy = AsyncMock()
    handler.set_current = AsyncMock()
    handler.async_request_data = AsyncMock()
    handler.async_set_energy = AsyncMock()
    handler.async_set_current = AsyncMock()
    handler.async_start = AsyncMock()
    handler.async_stop = AsyncMock()
    handler.async_enable_ev = AsyncMock()
    handler.async_disable_ev = AsyncMock()
    handler.async_set_failsafe = AsyncMock()
    handler.device_name = "KC-P30"
    handler.device_id = "keba_wallbox_12345678"
    handler.rfid = ""
    handler.get_value = MagicMock(side_effect=_KEBA_DATA.get)
    handler.add_update_listener = MagicMock(side_effect=lambda cb: cb())
    handler.start_periodic_request = MagicMock()
    handler.stop_periodic_request = MagicMock()
    with (
        patch("homeassistant.components.keba.KebaHandler", return_value=handler),
        patch(
            "homeassistant.components.keba.config_flow.KebaHandler",
            return_value=handler,
        ),
    ):
        yield handler


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_keba: MagicMock,
) -> MockConfigEntry:
    """Set up the KEBA integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
