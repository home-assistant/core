"""Test the eurotronic_cometblue sensor platform."""

from unittest.mock import patch

from eurotronic_cometblue_ha import InvalidByteValueError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "sensor.comet_blue_aa_bb_cc_dd_ee_ff_battery"


async def test_sensor_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_data_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that update data errors are handled and retried."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert (state := hass.states.get(ENTITY_ID))
    assert float(state.state) == 52.0

    # Fail with InvalidByteError on battery.
    # Should not raise UpdateFailed after 3 retries and keep old data.
    with patch(
        "homeassistant.components.eurotronic_cometblue.coordinator.AsyncCometBlue.get_battery_async",
        side_effect=InvalidByteValueError("Invalid byte"),
    ) as mock_get_battery:
        await mock_config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert mock_get_battery.call_count == 1
        assert mock_config_entry.runtime_data.last_update_success is True
        assert (state := hass.states.get(ENTITY_ID))
        assert float(state.state) == 52.0
