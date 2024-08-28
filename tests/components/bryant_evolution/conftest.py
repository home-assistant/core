"""Common fixtures for the Bryant Evolution tests."""

from collections.abc import Generator, Mapping
from unittest.mock import AsyncMock, patch

from evolutionhttp import BryantEvolutionLocalClient
import pytest

from homeassistant.components.bryant_evolution.const import CONF_SYSTEM_ZONE, DOMAIN
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bryant_evolution.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


DEFAULT_SYSTEM_ZONES = ((1, 1), (1, 2), (2, 3))
"""
A tuple of (system, zone) pairs representing the default system and zone configurations
for the Bryant Evolution integration.
"""


@pytest.fixture(autouse=True)
def mock_evolution_client_factory() -> Generator[AsyncMock]:
    """Mock an Evolution client."""
    with patch(
        "evolutionhttp.BryantEvolutionLocalClient.get_client",
        austospec=True,
    ) as mock_get_client:
        clients: Mapping[tuple[int, int], AsyncMock] = {}
        for system, zone in DEFAULT_SYSTEM_ZONES:
            clients[(system, zone)] = AsyncMock(spec=BryantEvolutionLocalClient)
            client = clients[system, zone]
            client.read_zone_name.return_value = f"System {system} Zone {zone}"
            client.read_current_temperature.return_value = 75
            client.read_hvac_mode.return_value = ("COOL", False)
            client.read_fan_mode.return_value = "AUTO"
            client.read_cooling_setpoint.return_value = 72
            mock_get_client.side_effect = lambda system, zone, tty: clients[
                (system, zone)
            ]
        yield mock_get_client


@pytest.fixture
async def mock_evolution_entry(
    hass: HomeAssistant,
    mock_evolution_client_factory: AsyncMock,
) -> MockConfigEntry:
    """Configure and return a Bryant evolution integration."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        entry_id="01J3XJZSTEF6G5V0QJX6HBC94T",  # For determinism in snapshot tests
        domain=DOMAIN,
        data={CONF_FILENAME: "/dev/ttyUSB0", CONF_SYSTEM_ZONE: [(1, 1)]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
