"""Common fixtures for Grandstream Home tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry with MAC unique_id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="GDS3710 EC74D79753C5",
        unique_id="ec:74:d7:97:53:c5",
        data={
            "host": "192.168.1.100",
            "username": "gdsha",
            "password": "password",
            "type": "GDS",
            "port": 443,
            "verify_ssl": False,
        },
    )


@pytest.fixture
def mock_gds_api() -> Generator[MagicMock]:
    """Mock Grandstream API and related functions."""
    api_instance = MagicMock()
    api_instance.device_mac = "00:0B:82:12:34:56"
    api_instance.version = "1.0.0"
    api_instance.host = "192.168.1.100"
    api_instance.product_model = "GDS3710"

    with (
        patch(
            "homeassistant.components.grandstream_home.create_api_instance",
            return_value=api_instance,
        ) as mock_create,
        patch(
            "homeassistant.components.grandstream_home.config_flow.create_api_instance",
            new=mock_create,
        ),
        patch(
            "homeassistant.components.grandstream_home.attempt_login",
            return_value=(True, None),
        ) as mock_login,
        patch(
            "homeassistant.components.grandstream_home.config_flow.attempt_login",
            new=mock_login,
        ),
        patch(
            "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
            return_value={
                "phone_status": "available",
                "version": "1.0.0",
            },
        ),
    ):
        yield api_instance


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gds_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Grandstream Home integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
