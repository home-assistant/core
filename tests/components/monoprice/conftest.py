"""Common fixtures for the Monoprice tests."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import MagicMock, patch

from pymonoprice import Monoprice, ZoneStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from serialx import SerialException

from homeassistant.components.monoprice.const import CONF_SOURCES, DOMAIN
from homeassistant.const import CONF_PORT


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JMONOPRICE00000000000000",
        data={CONF_PORT: "fake port", CONF_SOURCES: {"1": "one", "3": "three"}},
    )


@pytest.fixture
def mock_monoprice() -> Generator[MagicMock]:
    """Mock an amplifier that only answers for the zones of its first unit.

    The status of each zone can be changed in `zones`. The tone controls are
    deliberately not at their centre, to catch mixed up values.
    """
    zones = {
        zone_id: ZoneStatus(
            zone=zone_id,
            pa=False,
            power=True,
            mute=False,
            do_not_disturb=False,
            volume=10,
            treble=4,
            bass=9,
            balance=15,
            source=1,
            keypad=False,
        )
        for zone_id in range(11, 17)
    }
    zones[12].power = False

    def zone_status(zone_id: int) -> ZoneStatus:
        if zone_id not in zones:
            raise SerialException
        return replace(zones[zone_id])

    client = MagicMock(spec=Monoprice)
    client.zones = zones
    client.zone_status.side_effect = zone_status
    client.set_bass.side_effect = lambda zone_id, bass: setattr(
        zones[zone_id], "bass", bass
    )
    client.set_treble.side_effect = lambda zone_id, treble: setattr(
        zones[zone_id], "treble", treble
    )
    client.set_balance.side_effect = lambda zone_id, balance: setattr(
        zones[zone_id], "balance", balance
    )

    with patch("homeassistant.components.monoprice.get_monoprice", return_value=client):
        yield client
