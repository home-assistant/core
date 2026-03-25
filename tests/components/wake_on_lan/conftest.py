"""Test fixtures for Wake on Lan."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_MAC = "00:01:02:03:04:05"


@pytest.fixture
def mock_send_magic_packet() -> Generator[AsyncMock]:
    """Mock magic packet."""
    with patch("wakeonlan.send_magic_packet") as mock_send:
        yield mock_send


@pytest.fixture
def subprocess_call_return_value() -> int | None:
    """Return value for subprocess."""
    return 1


@pytest.fixture(autouse=True)
def mock_subprocess_call(subprocess_call_return_value: int) -> Generator[MagicMock]:
    """Mock magic packet."""
    with patch("homeassistant.components.wake_on_lan.switch.sp.call") as mock_sp:
        mock_sp.return_value = subprocess_call_return_value
        yield mock_sp


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.wake_on_lan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return {
        CONF_MAC: DEFAULT_MAC,
        CONF_BROADCAST_ADDRESS: "255.255.255.255",
        CONF_BROADCAST_PORT: 9,
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Statistics integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Wake on LAN {DEFAULT_MAC}",
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
