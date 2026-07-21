"""Tests for the solax sensor platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from solax.inverter import InverterError, InverterResponse
from solax.inverters import X1MiniV34

from homeassistant.components.solax import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


def __mock_get_data() -> InverterResponse:
    return InverterResponse(
        data=dict.fromkeys(X1MiniV34.sensor_map(), 0),
        dongle_serial_number="ABCDEFGHIJ",
        version="2.034.06",
        type=4,
        inverter_serial_number="XXXXXXX",
    )


async def test_coordinator_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an InverterError during a refresh marks the entities unavailable."""
    mock_config_entry.add_to_hass(hass)

    inverter = next(
        iter(
            X1MiniV34.build_all_variants(
                mock_config_entry.data[CONF_IP_ADDRESS],
                mock_config_entry.data[CONF_PORT],
                mock_config_entry.data[CONF_PASSWORD],
            )
        )
    )

    with (
        patch("homeassistant.components.solax.discover", return_value=inverter),
        patch("solax.RealTimeAPI.get_data", return_value=__mock_get_data()),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # making sure the base state is actually healthy before the test run.
    assert (
        hass.states.get("sensor.solax_abcdefghij_network_voltage").state
        != STATE_UNAVAILABLE
    )

    with patch("solax.RealTimeAPI.get_data", side_effect=InverterError):
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.solax_abcdefghij_network_voltage").state
        == STATE_UNAVAILABLE
    )
