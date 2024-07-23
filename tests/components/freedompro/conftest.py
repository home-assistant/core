"""Fixtures for Freedompro integration tests."""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.freedompro.const import DOMAIN

from .const import DEVICES, DEVICES_STATE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.freedompro.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_freedompro():
    """Mock freedompro get_list and get_states."""
    with (
        patch(
            "homeassistant.components.freedompro.coordinator.get_list",
            return_value={
                "state": True,
                "devices": DEVICES,
            },
        ),
        patch(
            "homeassistant.components.freedompro.coordinator.get_states",
            return_value=DEVICES_STATE,
        ),
    ):
        yield


@pytest.fixture
async def init_integration(hass) -> MockConfigEntry:
    """Set up the Freedompro integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Feedompro",
        unique_id="0123456",
        data={
            "api_key": "gdhsksjdhcncjdkdjndjdkdmndjdjdkd",
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture
async def init_integration_no_state(hass) -> MockConfigEntry:
    """Set up the Freedompro integration in Home Assistant without state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Feedompro",
        unique_id="0123456",
        data={
            "api_key": "gdhsksjdhcncjdkdjndjdkdmndjdjdkd",
        },
    )

    with (
        patch(
            "homeassistant.components.freedompro.coordinator.get_list",
            return_value={
                "state": True,
                "devices": DEVICES,
            },
        ),
        patch(
            "homeassistant.components.freedompro.coordinator.get_states",
            return_value=[],
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def get_states_response_for_uid(uid: str) -> list[dict[str, Any]]:
    """Return a deepcopy of the device state list for specific uid."""
    return deepcopy([resp for resp in DEVICES_STATE if resp["uid"] == uid])
