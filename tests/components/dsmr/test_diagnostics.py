"""Test DSMR diagnostics."""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from dsmr_parser.obis_references import (
    CURRENT_ELECTRICITY_USAGE,
    ELECTRICITY_ACTIVE_TARIFF,
    GAS_METER_READING,
)
from dsmr_parser.objects import CosemObject, MBusObject, Telegram
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal("0.0"), "unit": "W"}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )
    telegram.add(
        GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "m³"},
            ],
        ),
        "GAS_METER_READING",
    )

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    result = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)
    assert result == snapshot
