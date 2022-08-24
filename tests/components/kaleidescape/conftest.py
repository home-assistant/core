"""Fixtures for Kaleidescape integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from kaleidescape import Dispatcher
from kaleidescape.device import Automation, Movie, Power, System
import pytest

from homeassistant.components.kaleidescape.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MOCK_HOST, MOCK_SERIAL

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def fixture_mock_device() -> Generator[None, AsyncMock, None]:
    """Return a mocked Kaleidescape device."""
    with patch(
        "homeassistant.components.kaleidescape.KaleidescapeDevice", autospec=True
    ) as mock:
        host = MOCK_HOST

        device = mock.return_value
        device.dispatcher = Dispatcher()
        device.host = host
        device.port = 10000
        device.serial_number = MOCK_SERIAL
        device.is_connected = True
        device.is_server_only = False
        device.is_movie_player = True
        device.is_music_player = False
        device.system = System(
            ip_address=host,
            serial_number=MOCK_SERIAL,
            type="Strato",
            protocol=16,
            kos_version="10.4.2-19218",
            friendly_name=f"Device {MOCK_SERIAL}",
            movie_zones=1,
            music_zones=1,
        )
        device.power = Power(state="standby", readiness="disabled", zone=["available"])
        device.movie = Movie()
        device.automation = Automation()

        yield device


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
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
