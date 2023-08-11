"""Test Discovergy diagnostics."""
from unittest.mock import patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.discovergy.const import GET_METERS, LAST_READING
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry diagnostics."""
    with patch("pydiscovergy.Discovergy.meters", return_value=GET_METERS), patch(
        "pydiscovergy.Discovergy.meter_last_reading", return_value=LAST_READING
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"] == {
        "entry_id": mock_config_entry.entry_id,
        "version": 1,
        "domain": "discovergy",
        "title": REDACTED,
        "data": {"email": REDACTED, "password": REDACTED},
        "options": {},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "unique_id": REDACTED,
        "disabled_by": None,
    }

    assert result["meters"] == [
        {
            "additional": {
                "administration_number": REDACTED,
                "current_scaling_factor": 1,
                "first_measurement_time": 1517569090926,
                "internal_meters": 1,
                "last_measurement_time": 1678430543742,
                "manufacturer_id": "TST",
                "printed_full_serial_number": REDACTED,
                "scaling_factor": 1,
                "voltage_scaling_factor": 1,
            },
            "full_serial_number": REDACTED,
            "load_profile_type": "SLP",
            "location": REDACTED,
            "measurement_type": "ELECTRICITY",
            "meter_id": "f8d610b7a8cc4e73939fa33b990ded54",
            "serial_number": REDACTED,
            "type": "TST",
        }
    ]

    assert result["readings"] == {
        "f8d610b7a8cc4e73939fa33b990ded54": {
            "time": "2023-03-10T07:32:06.702000",
            "values": {
                "energy": 119348699715000.0,
                "energy1": 2254180000.0,
                "energy2": 119346445534000.0,
                "energyOut": 55048723044000.0,
                "energyOut1": 0.0,
                "energyOut2": 0.0,
                "power": 531750.0,
                "power1": 142680.0,
                "power2": 138010.0,
                "power3": 251060.0,
                "voltage1": 239800.0,
                "voltage2": 239700.0,
                "voltage3": 239000.0,
            },
        }
    }
