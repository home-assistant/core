"""Tests for AIS tracker config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyais.messages import NMEAMessage
from pyais.stream import SocketStream
from syrupy import SnapshotAssertion

from homeassistant.components.ais_tracker.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


class MockUDPReceiver(SocketStream):
    """Mock UDP receiver."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the mock."""
        self.messages = [
            NMEAMessage(b"!AIVDM,1,1,,B,139f1wPP0CPwM>JM<3eiK?wf25KT,0*60"),
            NMEAMessage(
                b"!AIVDM,2,1,4,A,539f1w`00000@?GK;D1<<Phu=<H4DQ8D0000000t20=72t0Ht1P00000,0*6D"
                b"!AIVDM,2,2,4,A,000000000000000,2*20"
            ),
        ]
        socket = MagicMock()
        super().__init__(socket, preprocessor=None)

    def __iter__(self) -> Generator[NMEAMessage, None, None]:
        """Iterate over messages."""
        while True:
            yield from [self.messages.pop()]


async def test_init(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test init of AIS tracker component."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.ais_tracker.coordinator.UDPReceiver",
        new=MockUDPReceiver,
    ):
        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 8

    for state in states:
        assert state == snapshot(name=state.entity_id)
