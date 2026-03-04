"""Test fixtures for Hidromotic integration."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hidromotic.const import DOMAIN
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.1.250"
DEVICE_ID = "0x01"

CONFIG_ENTRY_DATA = {
    CONF_HOST: HOST,
}

MOCK_ZONES = {
    0: {
        "id": 0,
        "slot_id": 0,
        "estado": 0,
        "label": "Zone 1",
        "duracion": 30,
    },
    1: {
        "id": 1,
        "slot_id": 1,
        "estado": 0,
        "label": "Zone 2",
        "duracion": 45,
    },
}

MOCK_TANKS = {
    0: {
        "id": 0,
        "slot_id": 3,
        "estado": 0,
        "label": "Tank 1",
        "nivel": 0,
        "modo": 1,
    },
}

MOCK_PUMP = {
    "estado": 0,
    "pausa_externa": 0,
}

MOCK_DATA = {
    "is_mini": False,
    "pic_version": 400,
    "pic_id": DEVICE_ID,
    "zones": MOCK_ZONES,
    "tanks": MOCK_TANKS,
    "pump": MOCK_PUMP,
    "outputs": {},
    "auto_riego": True,
}


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
def config_entry_data() -> dict[str, Any]:
    """Fixture for MockConfigEntry data."""
    return CONFIG_ENTRY_DATA


@pytest.fixture
def config_entry(config_entry_data: dict[str, Any]) -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        unique_id=HOST,
        domain=DOMAIN,
        data=config_entry_data,
        title=f"CHI Smart ({HOST})",
    )


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Fixture to mock the HidromoticClient."""
    with patch(
        "homeassistant.components.hidromotic.HidromoticClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.refresh = AsyncMock()
        client.set_zone_state = AsyncMock()
        client.set_auto_riego = AsyncMock()
        client.register_callback = MagicMock(return_value=lambda: None)
        client.data = MOCK_DATA.copy()
        client.get_zones = MagicMock(return_value=MOCK_ZONES)
        client.get_tanks = MagicMock(return_value=MOCK_TANKS)
        client.get_pump = MagicMock(return_value=MOCK_PUMP)
        client.is_zone_on = MagicMock(return_value=False)
        client.is_tank_full = MagicMock(return_value=True)
        client.is_tank_empty = MagicMock(return_value=False)
        client.get_tank_level = MagicMock(return_value="full")
        client.is_auto_riego_on = MagicMock(return_value=True)
        yield client


@pytest.fixture
def mock_client_cannot_connect() -> Generator[MagicMock]:
    """Fixture to mock a client that cannot connect."""
    with patch(
        "homeassistant.components.hidromotic.HidromoticClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=False)
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture
def mock_config_flow_client() -> Generator[MagicMock]:
    """Fixture to mock client for config flow tests."""
    with patch(
        "homeassistant.components.hidromotic.config_flow.HidromoticClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.data = MOCK_DATA.copy()
        yield client


@pytest.fixture(autouse=True)
def setup_platforms(
    hass: HomeAssistant,
    platforms: list[str],
) -> Generator[None]:
    """Fixture for setting up the default platforms."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield
