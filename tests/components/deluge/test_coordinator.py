"""Test Deluge coordinator.py methods."""

from homeassistant.components.deluge.const import DelugeSensorType
from homeassistant.components.deluge.coordinator import count_states

from . import GET_TORRENT_STATES_RESPONSE


def test_get_count() -> None:
    """Tests count_states()."""

    states = count_states(GET_TORRENT_STATES_RESPONSE)

    assert states[DelugeSensorType.DOWNLOADING_COUNT_SENSOR.value] == 1
    assert states[DelugeSensorType.SEEDING_COUNT_SENSOR.value] == 2
