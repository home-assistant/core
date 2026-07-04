"""Test Utility Meter diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.components.utility_meter.sensor import ATTR_LAST_RESET
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2024-04-06 00:00:00+00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy Bill",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.input1",
            "tariffs": [
                "tariff0",
                "tariff1",
            ],
        },
        title="Energy Bill",
    )

    last_reset = "2024-04-05T00:00:00+00:00"

    # Set up the sensors restore data
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.energy_bill_tariff0",
                    "3",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "3",
                    },
                    "native_unit_of_measurement": "kWh",
                    "last_reset": last_reset,
                    "last_period": "0",
                    "last_valid_state": 3,
                    "status": "collecting",
                },
            ),
            (
                State(
                    "sensor.energy_bill_tariff1",
                    "7",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "7",
                    },
                    "native_unit_of_measurement": "kWh",
                    "last_reset": last_reset,
                    "last_period": "0",
                    "last_valid_state": 7,
                    "status": "paused",
                },
            ),
        ],
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
