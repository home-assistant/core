"""Fixtures for Trinnov Altitude integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.trinnov_altitude.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, MOCK_ID

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def fixture_mock_device() -> Generator[None, AsyncMock, None]:
    """Return a mocked TrinnovAltitude."""
    with patch(
        "homeassistant.components.trinnov_altitude.TrinnovAltitude", autospec=True
    ) as mock:
        altitude = mock.return_value
        altitude.connect = AsyncMock(return_value=None)
        altitude.disconnect = AsyncMock(return_value=None)
        altitude.host = MOCK_HOST
        altitude.id = MOCK_ID
        altitude.version = "VERSION"
        yield altitude


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_ID,
        version=1,
        data={CONF_HOST: MOCK_HOST},
    )


@pytest.fixture(name="mock_integration")
async def fixture_mock_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Return a mock ConfigEntry setup for Kaleidescape integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
