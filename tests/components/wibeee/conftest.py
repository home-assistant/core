"""Test fixtures for Wibeee integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.wibeee.const import (
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Mock data constants
# ---------------------------------------------------------------------------

MOCK_HOST = "192.168.1.100"
MOCK_MAC = "001ec0112233"
MOCK_WIBEEE_ID = "WIBEEE"
MOCK_MODEL = "WBT"
MOCK_FIRMWARE = "4.4.199"


# ---------------------------------------------------------------------------
# Config entry fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 2233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={
            CONF_UPDATE_MODE: MODE_LOCAL_PUSH,
        },
        version=2,
    )


@pytest.fixture
def get_config() -> dict:
    """Return configuration for config flow tests."""
    return {
        CONF_HOST: MOCK_HOST,
    }


@pytest.fixture
def get_config_options() -> dict:
    """Return configuration for options flow tests."""
    return {
        CONF_UPDATE_MODE: MODE_POLLING,
        CONF_SCAN_INTERVAL: 30,
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Wibeee integration in Home Assistant."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wibeee.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


# ---------------------------------------------------------------------------
# API mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_wibeee_api() -> Generator[MagicMock]:
    """Mock the WibeeeAPI class."""
    with patch(
        "homeassistant.components.wibeee.WibeeeAPI",
        autospec=True,
    ) as mock_cls:
        api = MagicMock()
        api.async_check_connection = AsyncMock(return_value=True)
        api.async_fetch_device_info = AsyncMock(
            return_value=MagicMock(
                wibeee_id=MOCK_WIBEEE_ID,
                mac_addr=MOCK_MAC,
                mac_addr_formatted=MOCK_MAC.upper(),
                mac_addr_short="2233",
                model=MOCK_MODEL,
                firmware_version=MOCK_FIRMWARE,
                ip_addr=MOCK_HOST,
            )
        )
        api.async_fetch_status = AsyncMock(
            return_value={
                "fase1_vrms": "230.50",
                "fase1_irms": "2.30",
                "fase1_p_activa": "277.00",
                "fase1_energia_activa": "12345",
                "model": MOCK_MODEL,
                "webversion": MOCK_FIRMWARE,
            }
        )
        api.host = MOCK_HOST

        mock_cls.return_value = api
        yield api


@pytest.fixture
def mock_wibeee_api_config_flow() -> Generator[MagicMock]:
    """Mock the WibeeeAPI class for config flow tests."""
    with patch(
        "homeassistant.components.wibeee.config_flow.WibeeeAPI",
        autospec=True,
    ) as mock_cls:
        api = MagicMock()
        api.async_check_connection = AsyncMock(return_value=True)
        api.async_fetch_device_info = AsyncMock(
            return_value=MagicMock(
                wibeee_id=MOCK_WIBEEE_ID,
                mac_addr=MOCK_MAC,
                mac_addr_formatted=MOCK_MAC.upper(),
                mac_addr_short="2233",
                model=MOCK_MODEL,
                firmware_version=MOCK_FIRMWARE,
                ip_addr=MOCK_HOST,
            )
        )
        api.host = MOCK_HOST

        mock_cls.return_value = api
        yield api
