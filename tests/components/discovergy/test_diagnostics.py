"""Test Discovergy diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"] == {
        "entry_id": entry.entry_id,
        "version": 1,
        "domain": "discovergy",
        "title": "user@example.org",
        "data": {"email": REDACTED, "password": REDACTED},
        "options": {},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "unique_id": "user@example.org",
        "disabled_by": None,
    }

    assert result["meters"] == [
        {
            "additional": {
                "administrationNumber": REDACTED,
                "currentScalingFactor": 1,
                "firstMeasurementTime": 1517569090926,
                "fullSerialNumber": REDACTED,
                "internalMeters": 1,
                "lastMeasurementTime": 1678430543742,
                "loadProfileType": "SLP",
                "manufacturerId": "TST",
                "printedFullSerialNumber": REDACTED,
                "scalingFactor": 1,
                "type": "TST",
                "voltageScalingFactor": 1,
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
