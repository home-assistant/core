"""Fixtures for Trinnov Altitude integration."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.trinnov_altitude.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, MOCK_ID, MOCK_MAC

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def fixture_mock_device() -> Generator[AsyncMock, None, None]:
    """Return a mocked TrinnovAltitude."""
    with (
        patch(
            "homeassistant.components.trinnov_altitude.TrinnovAltitudeClient",
            autospec=True,
        ) as init_mock,
        patch(
            "homeassistant.components.trinnov_altitude.config_flow.TrinnovAltitudeClient",
            autospec=True,
        ) as flow_mock,
    ):
        altitude = init_mock.return_value
        flow_mock.return_value = altitude
        altitude.start = AsyncMock(return_value=None)
        altitude.wait_synced = AsyncMock(return_value=None)
        altitude.stop = AsyncMock(return_value=None)
        altitude.power_off = AsyncMock(return_value=None)
        altitude.mute_set = AsyncMock(return_value=None)
        altitude.source_set_by_name = AsyncMock(return_value=None)
        altitude.volume_up = AsyncMock(return_value=None)
        altitude.volume_down = AsyncMock(return_value=None)
        altitude.volume_set = AsyncMock(return_value=None)
        altitude.volume_percentage_set = AsyncMock(return_value=None)
        altitude.power_on_available.return_value = True
        altitude.power_on.return_value = None
        altitude.volume_percentage = 50.0
        altitude.host = MOCK_HOST
        altitude.connected = True
        altitude.state = SimpleNamespace(
            id=MOCK_ID,
            version="VERSION",
            synced=True,
            source="Apple TV",
            sources={0: "Apple TV", 1: "Blu-ray"},
            source_format="PCM",
            mute=False,
            volume=-35.0,
        )
        yield altitude


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_ID,
        version=1,
        data={CONF_HOST: MOCK_HOST, CONF_MAC: MOCK_MAC},
    )


@pytest.fixture(name="mock_integration")
async def fixture_mock_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Return a mock ConfigEntry setup for Trinnov Altitude integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
